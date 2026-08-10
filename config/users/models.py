from django.conf import settings
from django.db import models
from django.utils import timezone


class UserProfile(models.Model):
    USER_TYPE_CHOICES = [
        ("padrao", "Padrão"),
        ("produtor", "Produtor"),
        ("veterinario", "Veterinario"),
        ("estudante", "Estudante"),
        ("pesquisador", "Pesquisador"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    user_type = models.CharField(max_length=30, choices=USER_TYPE_CHOICES, default="padrao")
    photo = models.FileField(upload_to="profiles/", blank=True)
    phone = models.CharField(max_length=30, blank=True)
    institution = models.CharField(max_length=180, blank=True)
    role = models.CharField(max_length=120, blank=True)
    crmv = models.CharField(max_length=40, blank=True)
    city = models.CharField(max_length=120, blank=True)
    state = models.CharField(max_length=2, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__username"]

    def __str__(self):
        return f"Perfil de {self.user.get_username()}"


class PasswordResetCode(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="password_reset_codes",
    )
    code_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["expires_at", "used_at"]),
        ]

    @property
    def is_available(self):
        return self.used_at is None and self.expires_at > timezone.now()

    def mark_used(self):
        self.used_at = timezone.now()
        self.save(update_fields=["used_at"])
