from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from .models import PasswordResetCode, UserProfile

User = get_user_model()


class UserProfileSerializer(serializers.ModelSerializer):
    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = [
            "user_type",
            "photo",
            "photo_url",
            "phone",
            "institution",
            "role",
            "crmv",
            "city",
            "state",
        ]
        read_only_fields = ["photo_url"]

    def get_photo_url(self, profile):
        if not profile.photo:
            return ""

        request = self.context.get("request")
        url = profile.photo.url
        return request.build_absolute_uri(url) if request else url


class UserSerializer(serializers.ModelSerializer):
    profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "profile"]

    def get_profile(self, user):
        profile, _ = UserProfile.objects.get_or_create(user=user)
        return UserProfileSerializer(profile, context=self.context).data


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150, required=False, allow_blank=True)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    profile = UserProfileSerializer(required=False)

    def validate_email(self, value):
        email = value.strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("Ja existe um usuario com este e-mail.")
        return email

    def validate_username(self, value):
        username = value.strip()
        if username and User.objects.filter(username__iexact=username).exists():
            raise serializers.ValidationError("Ja existe um usuario com este nome de usuario.")
        return username

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "As senhas nao conferem."})
        validate_password(attrs["password"])
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        profile_data = validated_data.pop("profile", {})
        password = validated_data.pop("password")
        validated_data.pop("password_confirm")

        email = validated_data["email"]
        username = validated_data.pop("username", "") or email
        user = User.objects.create_user(username=username, password=password, **validated_data)
        profile, _ = UserProfile.objects.get_or_create(user=user)
        for field, value in profile_data.items():
            setattr(profile, field, value)
        profile.save()
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs["email"].strip().lower()
        password = attrs["password"]
        user = User.objects.filter(email__iexact=email).first()

        if not user:
            raise serializers.ValidationError("E-mail ou senha invalidos.")

        authenticated_user = authenticate(
            request=self.context.get("request"),
            username=user.get_username(),
            password=password,
        )
        if not authenticated_user:
            raise serializers.ValidationError("E-mail ou senha invalidos.")
        if not authenticated_user.is_active:
            raise serializers.ValidationError("Usuario inativo.")

        attrs["user"] = authenticated_user
        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.strip().lower()


class PasswordResetConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6, min_length=6)
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    def validate_email(self, value):
        return value.strip().lower()

    def validate_code(self, value):
        code = value.strip()
        if not code.isdigit():
            raise serializers.ValidationError("Informe o codigo de 6 digitos.")
        return code

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "As senhas nao conferem."})

        user = User.objects.filter(email__iexact=attrs["email"], is_active=True).first()
        if not user:
            raise serializers.ValidationError("Codigo invalido ou expirado.")

        validate_password(attrs["password"], user=user)

        reset_codes = PasswordResetCode.objects.filter(
            user=user,
            used_at__isnull=True,
            expires_at__gt=timezone.now(),
        ).order_by("-created_at")

        for reset_code in reset_codes:
            if reset_code.is_available and self.context["check_code"](attrs["code"], reset_code.code_hash):
                attrs["user"] = user
                attrs["reset_code"] = reset_code
                return attrs

        raise serializers.ValidationError("Codigo invalido ou expirado.")


class UpdateUserSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    user_type = serializers.ChoiceField(
        choices=UserProfile.USER_TYPE_CHOICES,
        required=False,
        allow_blank=False,
    )
    photo = serializers.FileField(required=False, allow_empty_file=False)
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True)
    institution = serializers.CharField(max_length=180, required=False, allow_blank=True)
    role = serializers.CharField(max_length=120, required=False, allow_blank=True)
    crmv = serializers.CharField(max_length=40, required=False, allow_blank=True)
    city = serializers.CharField(max_length=120, required=False, allow_blank=True)
    state = serializers.CharField(max_length=2, required=False, allow_blank=True)

    @transaction.atomic
    def update(self, instance, validated_data):
        profile_fields = [
            "user_type",
            "photo",
            "phone",
            "institution",
            "role",
            "crmv",
            "city",
            "state",
        ]
        profile_data = {
            field: validated_data.pop(field)
            for field in profile_fields
            if field in validated_data
        }

        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()

        if profile_data:
            profile, _ = UserProfile.objects.get_or_create(user=instance)
            for field, value in profile_data.items():
                setattr(profile, field, value)
            profile.save()

        return instance
