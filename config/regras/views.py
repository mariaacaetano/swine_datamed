from rest_framework.response import Response
from rest_framework.views import APIView

from .engine import MotorRegras


class InferenciaRegrasView(APIView):
    def post(self, request):
        return Response(MotorRegras().inferir(request.data.get("texto", "")))
