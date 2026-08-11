from rest_framework.response import Response
from rest_framework.views import APIView

from .engine import MotorSemantico


class InferenciaSemanticaView(APIView):
    def post(self, request):
        return Response(MotorSemantico().inferir(request.data.get("texto", "")))
