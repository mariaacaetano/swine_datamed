from rest_framework import serializers

from .models import MedicationApplication, Pig


class MedicationApplicationSerializer(serializers.ModelSerializer):
    pig_name = serializers.CharField(source="pig.name", read_only=True)

    class Meta:
        model = MedicationApplication
        fields = [
            "id",
            "pig",
            "pig_name",
            "medicine_name",
            "active_principle",
            "dose",
            "route",
            "applied_at",
            "withdrawal_until",
            "responsible",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate_pig(self, pig):
        request = self.context.get("request")
        if request and pig.owner != request.user:
            raise serializers.ValidationError("Este suino nao pertence ao usuario autenticado.")
        return pig


class PigSerializer(serializers.ModelSerializer):
    photo_url = serializers.SerializerMethodField()
    medications_count = serializers.IntegerField(read_only=True)
    last_medication = serializers.SerializerMethodField()

    class Meta:
        model = Pig
        fields = [
            "id",
            "name",
            "tag",
            "breed",
            "sex",
            "life_stage",
            "size_category",
            "pen",
            "origin",
            "birth_date",
            "weight_kg",
            "status",
            "notes",
            "photo",
            "photo_url",
            "medications_count",
            "last_medication",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at", "photo_url", "medications_count", "last_medication"]

    def get_photo_url(self, pig):
        if not pig.photo:
            return ""

        request = self.context.get("request")
        url = pig.photo.url
        return request.build_absolute_uri(url) if request else url

    def get_last_medication(self, pig):
        medication = pig.medications.order_by("-applied_at", "-created_at").first()
        if not medication:
            return None
        return MedicationApplicationSerializer(medication, context=self.context).data
