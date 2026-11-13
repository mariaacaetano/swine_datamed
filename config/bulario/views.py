from rest_framework import serializers, viewsets
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import CasoClinico, Doenca, Farmaco, GeracaoDataset, Sintoma, Vacina, Variavel
from .serializers import (CasoClinicoSerializer, DoencaSerializer, FarmacoSerializer,
                          GeracaoDatasetSerializer, SintomaSerializer, VacinaSerializer, VariavelSerializer)
from .utils import normalize, score_farmaco
from .triage import compare, pipeline_status, triage
from .presentation import _adicionar_graus_avaliacao
from .serializers import TriageInputSerializer
from .pagination import StandardPagination


def disease_hints_for_query(query):
    normalized_query = normalize(query)
    if not normalized_query:
        return []

    hints = set()

    for sintoma in Sintoma.objects.prefetch_related("doencas"):
        symptom = normalize(sintoma.nome)
        if symptom and (symptom in normalized_query or normalized_query in symptom):
            hints.update(sintoma.doencas.all())

    for doenca in Doenca.objects.all():
        text = normalize(" ".join([doenca.nome, doenca.sintomas_texto, doenca.tipo, doenca.fase_comum]))
        if normalized_query in text:
            hints.add(doenca)

    return list(hints)


class FarmacoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Farmaco.objects.prefetch_related("doencas_relacionadas__sintomas").all()
    serializer_class = FarmacoSerializer
    lookup_field = "id"

    def get_queryset(self):
        return super().get_queryset().completos()

    @action(detail=False, methods=["get"])
    def buscar(self, request):
        query = request.query_params.get("q", "")
        disease_hints = disease_hints_for_query(query)
        scored = [
            (farmaco, score_farmaco(farmaco, query, disease_hints))
            for farmaco in self.get_queryset()
        ]
        results = [
            farmaco
            for farmaco, score in sorted(scored, key=lambda item: (-item[1], item[0].nome_comercial))
            if score > 0
        ]

        return Response(
            {
                "query": query,
                "disease_hints": DoencaSerializer(disease_hints, many=True).data,
                "results": FarmacoSerializer(results, many=True).data,
            }
        )


class SintomaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Sintoma.objects.prefetch_related("doencas").all()
    serializer_class = SintomaSerializer


class DoencaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Doenca.objects.prefetch_related("sintomas").all()
    serializer_class = DoencaSerializer


class VariavelViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Variavel.objects.all()
    serializer_class = VariavelSerializer


class VacinaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Vacina.objects.all()
    serializer_class = VacinaSerializer


class CasoClinicoViewSet(viewsets.ReadOnlyModelViewSet):
    pagination_class = StandardPagination
    queryset = CasoClinico.objects.select_related("doenca", "geracao").prefetch_related("doenca__sintomas").all()
    serializer_class = CasoClinicoSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        generation = self.request.query_params.get("geracao")
        if generation and not generation.isdigit():
            raise serializers.ValidationError({"geracao": "Informe um identificador numérico."})
        return queryset.filter(geracao_id=generation) if generation else queryset


class PreparacaoDadosView(APIView):
    """Seção do backend para importar a base e construir o dataset reproduzível."""

    def get_permissions(self):
        return [AllowAny()] if self.request.method == "GET" else [IsAdminUser()]

    def get(self, request):
        latest = GeracaoDataset.objects.first()
        return Response({
            "base": {"doencas": Doenca.objects.count(), "sintomas": Sintoma.objects.count(),
                     "variaveis": Variavel.objects.count(), "farmacos": Farmaco.objects.completos().count(), "vacinas": Vacina.objects.count()},
            "ultima_geracao": GeracaoDatasetSerializer(latest).data if latest else None,
        })

    def post(self, request):
        return Response({
            "erro": "A preparação é executada pelo comando administrativo import_swine_data.",
            "comando": "python config/manage.py import_swine_data --generate",
        }, status=405)


class TriagemView(APIView):
    permission_classes = [AllowAny]
    engine_key = None

    def post(self, request):
        serializer = TriageInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if self.engine_key:
            serializer.validated_data["mecanismo"] = self.engine_key
        return Response(triage(serializer.validated_data))


class ComparacaoInferenciaView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        serializer = TriageInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        text = serializer.validated_data["texto"]
        if not text:
            return Response({"erro": "Informe um texto para comparação."}, status=400)
        return Response(compare(text))


class PipelineStatusView(APIView):
    def get(self, request):
        return Response(pipeline_status())


class CatalogoView(APIView):
    def get(self, request):
        return Response({
            "farmacos": FarmacoSerializer(Farmaco.objects.completos().prefetch_related("doencas_relacionadas__sintomas"), many=True).data,
            "sintomas": SintomaSerializer(Sintoma.objects.all(), many=True).data,
            "doencas": DoencaSerializer(Doenca.objects.prefetch_related("sintomas"), many=True).data,
            "variaveis": VariavelSerializer(Variavel.objects.all(), many=True).data,
        })
