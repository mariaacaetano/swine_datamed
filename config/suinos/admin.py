from django.contrib import admin

from .models import MedicationApplication, Pig


class MedicationApplicationInline(admin.TabularInline):
    model = MedicationApplication
    extra = 0


@admin.register(Pig)
class PigAdmin(admin.ModelAdmin):
    list_display = ("name", "tag", "owner", "status", "sex", "weight_kg", "created_at")
    list_filter = ("status", "sex")
    search_fields = ("name", "tag", "owner__username", "owner__email")
    inlines = [MedicationApplicationInline]


@admin.register(MedicationApplication)
class MedicationApplicationAdmin(admin.ModelAdmin):
    list_display = ("medicine_name", "pig", "applied_at", "route", "withdrawal_until")
    list_filter = ("route", "applied_at")
    search_fields = ("medicine_name", "active_principle", "pig__name", "pig__tag")
