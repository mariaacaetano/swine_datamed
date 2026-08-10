from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import PasswordResetCode

User = get_user_model()


class AuthApiTests(APITestCase):
    def test_register_creates_user_profile_and_token(self):
        response = self.client.post(
            reverse("register"),
            {
                "email": "maria@example.com",
                "password": "SenhaForte123!",
                "password_confirm": "SenhaForte123!",
                "first_name": "Maria",
                "profile": {
                    "user_type": "veterinario",
                    "institution": "IFC",
                    "crmv": "12345",
                },
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("token", response.data)
        user = User.objects.get(email="maria@example.com")
        self.assertEqual(user.username, "maria@example.com")
        self.assertEqual(user.profile.user_type, "veterinario")

    def test_login_returns_existing_user_token(self):
        user = User.objects.create_user(
            username="joao@example.com",
            email="joao@example.com",
            password="SenhaForte123!",
        )
        self.assertTrue(hasattr(user, "profile"))

        response = self.client.post(
            reverse("login"),
            {"email": "joao@example.com", "password": "SenhaForte123!"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("token", response.data)

    def test_me_requires_authentication(self):
        response = self.client.get(reverse("me"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_user_can_update_profile(self):
        user = User.objects.create_user(
            username="ana@example.com",
            email="ana@example.com",
            password="SenhaForte123!",
        )
        self.client.force_authenticate(user=user)
        photo = SimpleUploadedFile("perfil.jpg", b"fake-image", content_type="image/jpeg")

        response = self.client.patch(
            reverse("me"),
            {
                "first_name": "Ana",
                "user_type": "padrao",
                "institution": "IFC",
                "role": "Pesquisadora",
                "city": "Araquari",
                "state": "SC",
                "photo": photo,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertEqual(user.first_name, "Ana")
        self.assertEqual(user.profile.user_type, "padrao")
        self.assertEqual(user.profile.institution, "IFC")
        self.assertTrue(user.profile.photo.name.startswith("profiles/"))

    def test_password_reset_sends_code_to_existing_user(self):
        User.objects.create_user(
            username="recuperar@example.com",
            email="recuperar@example.com",
            password="SenhaForte123!",
        )

        response = self.client.post(
            reverse("password-reset-request"),
            {"email": "recuperar@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(PasswordResetCode.objects.count(), 1)
        self.assertIn("codigo de recuperacao", mail.outbox[0].subject.lower())

    def test_password_reset_changes_password_with_valid_code(self):
        user = User.objects.create_user(
            username="trocar@example.com",
            email="trocar@example.com",
            password="SenhaForte123!",
        )
        self.client.post(
            reverse("password-reset-request"),
            {"email": "trocar@example.com"},
            format="json",
        )
        code = "".join(character for character in mail.outbox[0].body if character.isdigit())[:6]

        response = self.client.post(
            reverse("password-reset-confirm"),
            {
                "email": "trocar@example.com",
                "code": code,
                "password": "NovaSenha123!",
                "password_confirm": "NovaSenha123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertTrue(user.check_password("NovaSenha123!"))
        self.assertFalse(PasswordResetCode.objects.filter(user=user, used_at__isnull=True).exists())

    def test_password_reset_rejects_invalid_code(self):
        User.objects.create_user(
            username="codigo@example.com",
            email="codigo@example.com",
            password="SenhaForte123!",
        )

        response = self.client.post(
            reverse("password-reset-confirm"),
            {
                "email": "codigo@example.com",
                "code": "000000",
                "password": "NovaSenha123!",
                "password_confirm": "NovaSenha123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
