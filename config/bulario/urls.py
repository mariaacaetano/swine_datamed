from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (CasoClinicoViewSet, ComparacaoInferenciaView, DoencaViewSet, FarmacoViewSet, PreparacaoDadosView,
                    SintomaViewSet, TriagemView, VacinaViewSet, VariavelViewSet, CatalogoView, PipelineStatusView)

router = DefaultRouter()
router.register("farmacos", FarmacoViewSet, basename="farmaco")
router.register("sintomas", SintomaViewSet, basename="sintoma")
router.register("doencas", DoencaViewSet, basename="doenca")
router.register("variaveis", VariavelViewSet, basename="variavel")
router.register("vacinas", VacinaViewSet, basename="vacina")
router.register("casos-clinicos", CasoClinicoViewSet, basename="caso-clinico")

urlpatterns = [
    path("catalogo/", CatalogoView.as_view(), name="catalogo"),
    path("pipeline/", PipelineStatusView.as_view(), name="pipeline"),
    path("", include(router.urls)),
    path("triagem/", TriagemView.as_view(), name="triagem"),
    path("comparacao-inferencia/", ComparacaoInferenciaView.as_view(), name="comparacao-inferencia"),
    path("preparacao-dados/", PreparacaoDadosView.as_view(), name="preparacao-dados"),
]
