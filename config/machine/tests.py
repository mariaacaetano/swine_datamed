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

    def test_bernoulli_partial_evidence_uses_only_observed_variables(self):
        import numpy as np
        from sklearn.naive_bayes import BernoulliNB
        model = BernoulliNB(alpha=1).fit([[1, 1], [1, 1], [0, 0], [0, 0]], ['A', 'A', 'B', 'B'])
        partial = MotorMachineLearning._predict_partial_bernoulli(model, np.array([[1, 0]]), np.array([True, False]))
        self.assertAlmostEqual(partial[0], 0.75)
        complete = MotorMachineLearning._predict_partial_bernoulli(model, np.array([[1, 0]]), np.array([True, True]))
        np.testing.assert_allclose(complete, model.predict_proba([[1, 0]])[0])
        empty = MotorMachineLearning._predict_partial_bernoulli(model, np.array([[1, 0]]), np.array([False, False]))
        np.testing.assert_allclose(empty, np.exp(model.class_log_prior_))

    def test_analytical_normalizes_before_limiting_hypotheses(self):
        tosse = Sintoma.objects.create(nome='Tosse')
        for name in ['A', 'B']:
            disease = Doenca.objects.create(nome=name)
            disease.sintomas.add(tosse)
        with patch.object(MotorMachineLearning, '_load_artifact', return_value=None):
            result = MotorMachineLearning().inferir('tosse', limite=1)
        self.assertEqual(len(result['hipoteses']), 1)
        self.assertAlmostEqual(result['hipoteses'][0]['score'], 0.5)
