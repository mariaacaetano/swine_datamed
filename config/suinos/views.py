from django.db.models import Count
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import MedicationApplication, Pig
from .serializers import MedicationApplicationSerializer, PigSerializer


class PigViewSet(viewsets.ModelViewSet):
    serializer_class = PigSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get_queryset(self):
        return (
            Pig.objects.filter(owner=self.request.user)
            .annotate(medications_count=Count("medications"))
            .prefetch_related("medications")
        )

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=["get", "post"], url_path="medicacoes")
    def medications(self, request, pk=None):
        pig = self.get_object()

        if request.method == "GET":
            serializer = MedicationApplicationSerializer(
                pig.medications.all(),
                many=True,
                context={"request": request},
            )
            return Response(serializer.data)

        serializer = MedicationApplicationSerializer(
            data={**request.data, "pig": pig.id},
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class MedicationApplicationViewSet(viewsets.ModelViewSet):
    serializer_class = MedicationApplicationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = MedicationApplication.objects.filter(pig__owner=self.request.user).select_related("pig")
        pig_id = self.request.query_params.get("pig")
        if pig_id:
            queryset = queryset.filter(pig_id=pig_id)
        return queryset
