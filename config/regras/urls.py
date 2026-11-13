from django.urls import path

from .views import InferenciaRegrasView, InferenciaRegrasEncadeadasView

urlpatterns = [
    path("inferir/", InferenciaRegrasView.as_view(), name="inferencia-regras"),
    path("encadeadas/inferir/", InferenciaRegrasEncadeadasView.as_view(), name="inferencia-regras-encadeadas"),
]
