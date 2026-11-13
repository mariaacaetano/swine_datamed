import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd
from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from bulario.knowledge_engines import MotorBayesiano, MotorFuzzy
from bulario.models import Doenca, Sintoma
from machine.engine import MotorMachineLearning
from regras.engine import MotorRegras
from regras.chaining import MotorRegrasEncadeadas
from semantica.engine import MotorSemantico


class ClassificationEvaluationTests(TestCase):
    def setUp(self):
        symptom = Sintoma.objects.create(nome="Perda de apetite")
        disease = Doenca.objects.create(nome="Enfermidade de teste")
        disease.sintomas.add(symptom)

    def test_classification_skips_therapeutic_queries_without_changing_hypotheses(self):
        engines = [MotorRegras(), MotorRegrasEncadeadas(), MotorSemantico(), MotorMachineLearning(), MotorBayesiano(), MotorFuzzy()]
        with patch.object(MotorMachineLearning, "_load_artifact", return_value=None):
            for engine in engines:
                with self.subTest(engine=engine.nome):
                    original = engine.inferir("Perda de apetite")
                    with CaptureQueriesContext(connection) as queries:
                        result = engine.inferir("Perda de apetite", incluir_indicacoes=False)
                    self.assertEqual(result["hipoteses"], original["hipoteses"])
                    self.assertEqual(result["farmacos_relacionados"], [])
                    self.assertFalse(any("bulario_farmaco" in query["sql"] for query in queries))

    def test_evaluator_preserves_compound_symptoms_and_counts_short_lists(self):
        with TemporaryDirectory() as directory:
            data = Path(directory) / "test.csv"
            output = Path(directory) / "metrics.json"
            pd.DataFrame([
                {"sintoma_001_perda_de_apetite": 1, "doenca_alvo": "Enfermidade de teste"},
                {"sintoma_001_perda_de_apetite": 1, "doenca_alvo": "Outro diagnóstico"},
            ]).to_csv(data, index=False)
            with patch.object(MotorMachineLearning, "_load_artifact", return_value=None):
                call_command("evaluate_classification", data=str(data), output=str(output), stdout=StringIO())
            report = json.loads(output.read_text())
        self.assertEqual(report["fases"], ["conversao", "classificacao"])
        self.assertIn("regras_encadeadas", report["modelos"])
        for values in report["modelos"].values():
            self.assertEqual(values["registros_teste"], 2)
            self.assertEqual(values["entradas_distintas"], 1)
            self.assertEqual(values["cobertura_conversao"], 1)
            self.assertEqual(values["verdadeiros_positivos"], 1)
            self.assertEqual(values["falsos_positivos"], 1)
            self.assertEqual(values["falsos_negativos"], 1)
            self.assertEqual(values["precisao_top_5"], 0.5)
            self.assertEqual(values["recall_top_5"], 0.5)
            self.assertEqual(values["f1_top_5"], 0.5)

    def test_all_models_command_uses_same_real_engines_and_counters(self):
        with TemporaryDirectory() as directory:
            data = Path(directory) / 'test.csv'
            output = Path(directory) / 'metrics.json'
            pd.DataFrame([{'sintoma_001_perda_de_apetite': 1,
                           'doenca_alvo': 'Enfermidade de teste'}]).to_csv(data, index=False)
            with patch.object(MotorMachineLearning, '_load_artifact', return_value=None):
                call_command('evaluate_all_models', data=str(data), output=str(output), stdout=StringIO())
            report = json.loads(output.read_text())
        self.assertEqual(len(report['modelos']), 8)
        self.assertEqual(report['protocolo'], 'inferencia_corrigida_v3')
        for values in report['modelos'].values():
            self.assertEqual(values['acuracia_top_1'], 1)
            self.assertEqual(values['precisao_top_5'], 1)

    def test_empty_dataset_is_rejected_without_creating_metrics(self):
        from django.core.management.base import CommandError
        with TemporaryDirectory() as directory:
            data = Path(directory) / 'empty.csv'
            output = Path(directory) / 'metrics.json'
            pd.DataFrame(columns=['sintoma_001_perda_de_apetite', 'doenca_alvo']).to_csv(data, index=False)
            with self.assertRaises(CommandError):
                call_command('evaluate_all_models', data=str(data), output=str(output), stdout=StringIO())
            self.assertFalse(output.exists())
