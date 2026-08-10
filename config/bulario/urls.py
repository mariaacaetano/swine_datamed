from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (CasoClinicoViewSet, DoencaViewSet, FarmacoViewSet, PreparacaoDadosView,
                    SintomaViewSet, TriagemView, VacinaViewSet, VariavelViewSet)

router = DefaultRouter()
router.register("farmacos", FarmacoViewSet, basename="farmaco")
router.register("sintomas", SintomaViewSet, basename="sintoma")
router.register("doencas", DoencaViewSet, basename="doenca")
router.register("variaveis", VariavelViewSet, basename="variavel")
router.register("vacinas", VacinaViewSet, basename="vacina")
router.register("casos-clinicos", CasoClinicoViewSet, basename="caso-clinico")

urlpatterns = [
    path("", include(router.urls)),
    path("triagem/", TriagemView.as_view(), name="triagem"),
    path("preparacao-dados/", PreparacaoDadosView.as_view(), name="preparacao-dados"),
]
