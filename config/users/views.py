import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import PasswordResetCode
from .serializers import (
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    UpdateUserSerializer,
    UserSerializer,
)


PASSWORD_RESET_CODE_TTL_MINUTES = 15
User = get_user_model()


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {"token": token.key, "user": UserSerializer(user).data},
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "user": UserSerializer(user).data})


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        user = User.objects.filter(email__iexact=email, is_active=True).first()

        if user:
            code = f"{secrets.randbelow(1000000):06d}"
            PasswordResetCode.objects.filter(user=user, used_at__isnull=True).update(used_at=timezone.now())
            PasswordResetCode.objects.create(
                user=user,
                code_hash=make_password(code),
                expires_at=timezone.now() + timedelta(minutes=PASSWORD_RESET_CODE_TTL_MINUTES),
            )
            send_mail(
                subject="Codigo de recuperacao - Swine DataMed",
                message=(
                    f"Seu codigo de recuperacao do Swine DataMed e: {code}\n\n"
                    f"Ele expira em {PASSWORD_RESET_CODE_TTL_MINUTES} minutos. "
                    "Se voce nao pediu essa recuperacao, ignore este e-mail."
                ),
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                recipient_list=[user.email],
                fail_silently=False,
            )

        return Response({
            "detail": "Se o e-mail estiver cadastrado, enviaremos um codigo de recuperacao."
        })


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(
            data=request.data,
            context={"check_code": check_password},
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        reset_code = serializer.validated_data["reset_code"]

        user.set_password(serializer.validated_data["password"])
        user.save(update_fields=["password"])
        reset_code.mark_used()
        PasswordResetCode.objects.filter(user=user, used_at__isnull=True).exclude(id=reset_code.id).update(
            used_at=timezone.now()
        )
        Token.objects.filter(user=user).delete()

        return Response({"detail": "Senha redefinida com sucesso."})


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get(self, request):
        return Response(UserSerializer(request.user, context={"request": request}).data)

    def patch(self, request):
        serializer = UpdateUserSerializer(instance=request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user, context={"request": request}).data)
