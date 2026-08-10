from django.conf import settings
from django.db import models
from django.db.models import Q


class Pig(models.Model):
    SEX_CHOICES = [
        ("macho", "Macho"),
        ("femea", "Femea"),
    ]

    STATUS_CHOICES = [
        ("ativo", "Ativo"),
        ("tratamento", "Em tratamento"),
        ("vendido", "Vendido"),
        ("obito", "Obito"),
    ]

    LIFE_STAGE_CHOICES = [
        ("leitao", "Leitao"),
        ("creche", "Creche"),
        ("crescimento", "Crescimento"),
        ("terminacao", "Terminacao"),
        ("matriz", "Matriz"),
        ("reprodutor", "Reprodutor"),
    ]

    SIZE_CHOICES = [
        ("pequeno", "Pequeno"),
        ("medio", "Medio"),
        ("grande", "Grande"),
    ]

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pigs")
    name = models.CharField(max_length=120)
    tag = models.CharField(max_length=80, blank=True)
    breed = models.CharField(max_length=120, blank=True)
    sex = models.CharField(max_length=10, choices=SEX_CHOICES, blank=True)
    life_stage = models.CharField(max_length=30, choices=LIFE_STAGE_CHOICES, blank=True)
    size_category = models.CharField(max_length=20, choices=SIZE_CHOICES, blank=True)
    pen = models.CharField(max_length=120, blank=True)
    origin = models.CharField(max_length=160, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    weight_kg = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ativo")
    notes = models.TextField(blank=True)
    photo = models.FileField(upload_to="pigs/", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "tag"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "tag"],
                condition=~Q(tag=""),
                name="unique_pig_tag_per_owner",
            )
        ]

    def __str__(self):
        return self.name


class MedicationApplication(models.Model):
    ROUTE_CHOICES = [
        ("oral", "Oral"),
        ("intramuscular", "Intramuscular"),
        ("subcutanea", "Subcutanea"),
        ("topica", "Topica"),
        ("outra", "Outra"),
    ]

    pig = models.ForeignKey(Pig, on_delete=models.CASCADE, related_name="medications")
    medicine_name = models.CharField(max_length=160)
    active_principle = models.CharField(max_length=160, blank=True)
    dose = models.CharField(max_length=120, blank=True)
    route = models.CharField(max_length=30, choices=ROUTE_CHOICES, default="outra")
    applied_at = models.DateField()
    withdrawal_until = models.DateField(null=True, blank=True)
    responsible = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-applied_at", "-created_at"]

    def __str__(self):
        return f"{self.medicine_name} - {self.pig}"
