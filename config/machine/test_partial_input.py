from unittest.mock import patch

import pandas as pd
from django.test import TestCase
from sklearn.compose import ColumnTransformer
from sklearn.naive_bayes import BernoulliNB
from sklearn.preprocessing import OneHotEncoder

from bulario.models import Doenca, Sintoma
from machine.engine import MotorMachineLearning


class TrainedPartialInputTests(TestCase):
    def setUp(self):
        symptom = Sintoma.objects.create(nome='Tosse')
        self.disease = Doenca.objects.create(nome='A')
        self.disease.sintomas.add(symptom)
        other = Doenca.objects.create(nome='B')
        other.sintomas.add(Sintoma.objects.create(nome='Febre'))
        self.symptoms = ['sintoma_001_tosse', 'sintoma_002_febre']
        self.features = [*self.symptoms, 'Idade']
        frame = pd.DataFrame([[1, 1, '22–70 dias'], [1, 1, '22–70 dias'],
                              [0, 0, '>180 dias'], [0, 0, '>180 dias']], columns=self.features)
        processor = ColumnTransformer([
            ('symptoms', 'passthrough', self.symptoms),
            ('clinical', OneHotEncoder(handle_unknown='ignore', sparse_output=True), ['Idade']),
        ])
        model = BernoulliNB(alpha=1).fit(processor.fit_transform(frame), ['A', 'A', 'B', 'B'])
        self.artifact = {'preprocessor': processor, 'model': model,
                         'feature_columns': self.features, 'symptom_columns': self.symptoms,
                         'categorical_columns': ['Idade'],
                         'metadata': {'modelo_selecionado': 'Bernoulli Naive Bayes', 'resultado_teste': {}}}

    def infer(self, text):
        with patch.object(MotorMachineLearning, '_load_artifact', return_value=self.artifact):
            return MotorMachineLearning().inferir(text, incluir_indicacoes=False)

    def test_omitted_and_uncertain_features_do_not_become_observed_absence(self):
        confirmed = self.infer('tosse')
        uncertain = self.infer('tosse. Talvez febre')
        self.assertEqual(confirmed['hipoteses'], uncertain['hipoteses'])
        self.assertAlmostEqual(confirmed['hipoteses'][0]['score'], 0.75)
        negated = self.infer('tosse; não apresenta febre')
        self.assertAlmostEqual(negated['hipoteses'][0]['score'], 0.5)

    def test_numeric_age_reaches_training_category(self):
        result = self.infer('40 dias de idade com tosse')
        self.assertEqual(result['variaveis_reconhecidas']['idade_categoria'], '22–70 dias')
        # Tosse e dois indicadores da categoria: odds de A/B = 3³.
        self.assertAlmostEqual(result['hipoteses'][0]['score'], 27 / 28, places=6)

    def test_unknown_clinical_category_is_marginalized(self):
        # Faixa existe no extrator, mas não no encoder desta pequena base.
        result = self.infer('10 dias de idade com tosse')
        self.assertAlmostEqual(result['hipoteses'][0]['score'], 0.75)

    def test_empty_input_abstains_in_trained_path(self):
        self.assertEqual(self.infer('animal saudável')['hipoteses'], [])

    def test_classes_without_documented_signs_are_excluded_and_remaining_mass_normalized(self):
        disease = Doenca.objects.get(nome='B')
        disease.sintomas.set([Sintoma.objects.create(nome='Não informado no documento')])
        result = self.infer('tosse')
        self.assertEqual([h['nome'] for h in result['hipoteses']], ['A'])
        self.assertEqual(result['hipoteses'][0]['score'], 1)
        self.assertIn('documentado', result['universo_classes'])
