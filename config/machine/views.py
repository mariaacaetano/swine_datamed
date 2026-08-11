from rest_framework.response import Response
from rest_framework.views import APIView
from pathlib import Path
import json
from django.conf import settings

from .engine import MotorMachineLearning


class InferenciaMachineLearningView(APIView):
    def post(self, request):
        return Response(MotorMachineLearning().inferir(request.data.get("texto", "")))


class StatusMachineLearningView(APIView):
    def get(self, request):
        path = Path(settings.BASE_DIR) / "machine" / "artifacts" / "metrics.json"
        if not path.exists():
            return Response({"treinado": False, "mensagem": "Execute manage.py train_ml."}, status=503)
        with path.open(encoding="utf-8") as handle:
            return Response({"treinado": True, **json.load(handle)})
