import csv
import tempfile
from pathlib import Path

from django.conf import settings
from django.test import TestCase

from .data_pipeline import generate_clinical_dataset, generate_dataset, generate_ml_dataset, import_base_data
from .clinical_input import extract_clinical_case
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
                                        "farmacos": 68, "vacinas": 4, "indicacoes": 86})
        self.assertTrue(Doenca.objects.filter(nome="Doença de Glässer").exists())
        self.assertTrue(Sintoma.objects.filter(nome="Icterícia").exists())
        self.assertEqual(Farmaco.objects.count(), 68)
        self.assertEqual(Vacina.objects.count(), 4)
        self.assertEqual(Indicacao.objects.count(), 86)

    def test_comparison_endpoint_is_not_available(self):
        response = self.client.post(
            "/api/comparacao-inferencia/",
            {"texto": "tosse e febre"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)

    def test_extracts_clinical_variables_and_tolerates_small_typos(self):
        case = extract_clinical_case(
            "Suínco macho adulto terminacao com febre 41, vomito e diarrei 24h"
        )
        symptoms = {item.nome for item in case["sintomas"]}
        self.assertIn("Febre alta", symptoms)
        self.assertIn("Vômito", symptoms)
        self.assertIn("Diarreia", symptoms)
        self.assertEqual(case["variaveis"]["temperatura_corporal_c"], 41)
        self.assertEqual(case["variaveis"]["fase_reprodutiva"], "Terminação")
        self.assertEqual(case["variaveis"]["genero"], "Macho inteiro")
        self.assertEqual(case["variaveis"]["duracao_categoria"], "1–3 dias")

    def test_understands_common_language_expressions(self):
        case = extract_clinical_case(
            "Ele ficou meio caidinho, não quis a ração, parece estar puxando o ar "
            "e as fezes ficaram bem aguadas."
        )
        symptoms = {item.nome for item in case["sintomas"]}
        self.assertIn("Apatia", symptoms)
        self.assertIn("Perda de apetite", symptoms)
        self.assertNotIn("Dispneia", symptoms)
        self.assertIn("Diarreia aquosa", symptoms)
        self.assertIn("Dispneia", case["sintomas_incertos"])

    def test_negated_symptom_is_not_used_as_positive_evidence(self):
        case = extract_clinical_case("O suíno não está com febre e não apresentou vômito.")
        symptoms = {item.nome for item in case["sintomas"]}
        self.assertNotIn("Febre", symptoms)
        self.assertNotIn("Vômito", symptoms)
        self.assertIn("Febre", case["sintomas_negados"])
        self.assertIn("Vômito", case["sintomas_negados"])

    def test_triage_collects_context_and_understands_short_age_answer(self):
        first = self.client.post(
            "/api/triagem/",
            {"texto": "leitão macho não quis a ração há 2 dias, febre de 40 e está caidinho",
             "mecanismo": "regras"},
            content_type="application/json",
        ).json()
        self.assertIsNotNone(first["pergunta_complementar"])
        self.assertEqual(first["pergunta_complementar"]["campo"], "idade_dias")

        second_response = self.client.post(
            "/api/triagem/",
            {"texto": "40 dias", "mecanismo": "regras", "contexto_clinico": first["contexto_clinico"],
             "pergunta_anterior": first["pergunta_complementar"], "perguntas_realizadas": first["perguntas_realizadas"]},
            content_type="application/json",
        )
        self.assertEqual(second_response.status_code, 200)
        second = second_response.json()
        self.assertEqual(second["variaveis_reconhecidas"]["idade_dias"], 40)
        self.assertNotEqual(second["pergunta_complementar"]["campo"], "idade_dias")

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
