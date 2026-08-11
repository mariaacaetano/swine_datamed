from django.urls import path

from .views import InferenciaSemanticaView

urlpatterns = [path("inferir/", InferenciaSemanticaView.as_view(), name="inferencia-semantica")]
