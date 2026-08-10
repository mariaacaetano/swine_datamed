import csv
import tempfile
from pathlib import Path

from django.conf import settings
from django.test import TestCase

from .data_pipeline import generate_clinical_dataset, generate_dataset, generate_ml_dataset, import_base_data
from .models import CasoClinico, Doenca, Farmaco, Indicacao, Sintoma, Vacina, Variavel
from .utils import clean_text, normalize, split_list


class TextCleaningTests(TestCase):
    def test_unicode_and_lists_are_standardized_without_losing_accents(self):
        self.assertEqual(clean_text("  Pneumonia\xa0enzoo\u0301tica  "), "Pneumonia enzoótica")
        self.assertEqual(normalize("Doença de Glässer"), "doenca de glasser")
        self.assertEqual(split_list("Tosse; Febre,  Apatia"), ["Tosse", "Febre", "Apatia"])


class DataPipelineTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.summary = import_base_data(settings.BASE_DIR.parent / "base_data", clear=True)

    def test_imports_updated_spreadsheets(self):
        self.assertEqual(self.summary, {"doencas": 112, "sintomas": 80, "variaveis": 52,
                                        "farmacos": 7, "vacinas": 2, "indicacoes": 30})
        self.assertTrue(Doenca.objects.filter(nome="Doença de Glässer").exists())
        self.assertTrue(Sintoma.objects.filter(nome="Icterícia").exists())
        self.assertEqual(Farmaco.objects.count(), 7)
        self.assertEqual(Vacina.objects.count(), 2)
        self.assertEqual(Indicacao.objects.count(), 30)

    def test_generates_all_unique_symptom_combinations(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dataset.csv"
            generation = generate_dataset(path, seed=42)
            self.assertEqual(CasoClinico.objects.filter(geracao=generation).count(), 2084)
            self.assertTrue(generation.resumo["combinacoes_exaustivas"])
            with path.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 2084)
            self.assertEqual(len({(row["doenca"], row["sintomas_presentes"]) for row in rows}), 2084)
            self.assertIn("quantidade_sintomas", rows[0])
            self.assertEqual(len([name for name in rows[0] if name.startswith("sintoma_")]), 80)

    def test_generates_expanded_clinical_dataset_with_explicit_missing_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "clinical.csv"
            generation = generate_clinical_dataset(path, variations_per_combination=2, seed=42)
            self.assertEqual(generation.total_registros, 4168)
            self.assertEqual(generation.resumo["combinacoes_base"], 2084)
            with path.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 4168)
            self.assertIn("Umidade ambiente (%)", rows[0])
            self.assertTrue(any(row["Umidade ambiente (%)"] == "Não informado" for row in rows))
            self.assertTrue(all(row["Diagnóstico confirmado"] == row["doenca"] for row in rows))

    def test_ml_dataset_has_grouped_splits_and_no_target_leakage_columns(self):
        with tempfile.TemporaryDirectory() as directory:
            summary = generate_ml_dataset(directory, variations_per_combination=2, seed=42)
            self.assertEqual(summary["total"], 4168)
            split_combinations = {}
            for split in ["treino", "validacao", "teste"]:
                with (Path(directory) / f"{split}.csv").open(encoding="utf-8-sig", newline="") as handle:
                    rows = list(csv.DictReader(handle))
                split_combinations[split] = {row["combinacao_id"] for row in rows}
                self.assertNotIn("Diagnóstico confirmado", rows[0])
                self.assertNotIn("Suspeita clínica inicial", rows[0])
                self.assertNotIn("Resultado laboratorial", rows[0])
                self.assertIn("doenca_alvo", rows[0])
            self.assertFalse(split_combinations["treino"] & split_combinations["validacao"])
            self.assertFalse(split_combinations["treino"] & split_combinations["teste"])
            self.assertFalse(split_combinations["validacao"] & split_combinations["teste"])
