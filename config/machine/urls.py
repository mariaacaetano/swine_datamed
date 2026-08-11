from django.urls import path

from .views import InferenciaMachineLearningView, StatusMachineLearningView

urlpatterns = [
    path("inferir/", InferenciaMachineLearningView.as_view(), name="inferencia-machine"),
    path("status/", StatusMachineLearningView.as_view(), name="status-machine"),
]
