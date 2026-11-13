from rest_framework.response import Response
from rest_framework.views import APIView
from bulario.views import TriagemView
from bulario.registry import DEFAULT_ENGINE, model_status


class InferenciaMachineLearningView(TriagemView):
    engine_key = DEFAULT_ENGINE


class StatusMachineLearningView(APIView):
    def get(self, request):
        result = model_status(DEFAULT_ENGINE)
        return Response({"treinado": result["disponivel"], **result}, status=200 if result["disponivel"] else 503)
