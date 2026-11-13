from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import MedicationApplication, Pig
from bulario.models import Farmaco
from bulario.tests_support import complete_medication_data

User = get_user_model()


class PigApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="maria@example.com",
            email="maria@example.com",
            password="SenhaForte123!",
        )
        self.other_user = User.objects.create_user(
            username="ana@example.com",
            email="ana@example.com",
            password="SenhaForte123!",
        )
        self.client.force_authenticate(user=self.user)
        Farmaco.objects.create(**complete_medication_data(nome_comercial="Ferro"))

    def test_user_can_create_pig(self):
        response = self.client.post(
            reverse("suino-list"),
            {"name": "Matriz 01", "tag": "A-01", "status": "ativo"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Pig.objects.get().owner, self.user)

    def test_user_only_lists_own_pigs(self):
        Pig.objects.create(owner=self.user, name="Leitao 01", tag="L-01")
        Pig.objects.create(owner=self.other_user, name="Leitao 02", tag="L-02")

        response = self.client.get(reverse("suino-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["name"], "Leitao 01")

    def test_user_can_register_medication_for_own_pig(self):
        pig = Pig.objects.create(owner=self.user, name="Matriz 01", tag="A-01")

        response = self.client.post(
            reverse("medicacao-list"),
            {
                "pig": pig.id,
                "medicine_name": "Ferro",
                "dose": "2 ml",
                "route": "intramuscular",
                "applied_at": "2026-06-02",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(MedicationApplication.objects.get().pig, pig)

    def test_user_cannot_register_medication_for_other_user_pig(self):
        pig = Pig.objects.create(owner=self.other_user, name="Matriz 02", tag="B-01")

        response = self.client.post(
            reverse("medicacao-list"),
            {
                "pig": pig.id,
                "medicine_name": "Ferro",
                "applied_at": "2026-06-02",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_both_medication_routes_reject_incomplete_and_unknown_products(self):
        pig = Pig.objects.create(owner=self.user, name="Matriz 03", tag="C-01")
        Farmaco.objects.create(nome_comercial="Ficha incompleta")
        for endpoint in [reverse("medicacao-list"), reverse("suino-medications", args=[pig.id])]:
            for name in ["Ficha incompleta", "Produto sem cadastro"]:
                with self.subTest(endpoint=endpoint, medicine=name):
                    response = self.client.post(endpoint, {"pig": pig.id, "medicine_name": name,
                        "applied_at": "2026-06-02"}, format="json")
                    self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                    self.assertIn("medicine_name", response.data)
        self.assertFalse(MedicationApplication.objects.exists())

    def test_nested_medication_route_accepts_complete_product(self):
        pig = Pig.objects.create(owner=self.user, name="Matriz 04", tag="D-01")
        response = self.client.post(reverse("suino-medications", args=[pig.id]),
            {"medicine_name": "Ferro", "applied_at": "2026-06-02"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(MedicationApplication.objects.get().medicine_name, "Ferro")
