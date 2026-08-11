from django.test import TestCase
from pathlib import Path
from unittest.mock import patch

from bulario.models import Doenca, Sintoma

from .engine import MotorMachineLearning


class MotorMachineLearningTests(TestCase):
    def test_classificador_retorna_probabilidades_normalizadas(self):
        tosse = Sintoma.objects.create(nome="Tosse")
        diarreia = Sintoma.objects.create(nome="Diarreia")
        respiratoria = Doenca.objects.create(nome="Respiratória")
        intestinal = Doenca.objects.create(nome="Intestinal")
        respiratoria.sintomas.add(tosse)
        intestinal.sintomas.add(diarreia)

        with patch.object(MotorMachineLearning, "artifact_path", Path("/arquivo/inexistente.joblib")):
            resultado = MotorMachineLearning().inferir("Tosse")

        self.assertEqual(resultado["hipoteses"][0]["nome"], "Respiratória")
        self.assertAlmostEqual(sum(item["score"] for item in resultado["hipoteses"]), 1, places=5)
