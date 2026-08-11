from django.urls import path

from .views import InferenciaRegrasView

urlpatterns = [path("inferir/", InferenciaRegrasView.as_view(), name="inferencia-regras")]
