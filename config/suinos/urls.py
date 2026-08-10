from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import MedicationApplicationViewSet, PigViewSet

router = DefaultRouter()
router.register("suinos", PigViewSet, basename="suino")
router.register("medicacoes", MedicationApplicationViewSet, basename="medicacao")

urlpatterns = [
    path("", include(router.urls)),
]
