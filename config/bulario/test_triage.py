from datetime import date
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from machine.engine import MotorMachineLearning
from .clinical_input import extract_clinical_case
from .data_pipeline import import_base_data
from .medications import select_medications
from .models import Doenca, Farmaco, Indicacao, Sintoma
from .triage import next_question
from suinos.models import MedicationApplication, Pig


class TriageConversationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        import_base_data(settings.BASE_DIR.parent / "base_data")

    def post(self, text, previous=None, **extra):
        data = {"texto": text, "mecanismo": "regras"}
        if previous:
            data.update({"contexto_clinico": previous["contexto_clinico"],
                         "pergunta_anterior": previous["pergunta_complementar"] or {},
                         "perguntas_realizadas": previous["perguntas_realizadas"]})
        response = self.client.post("/api/triagem/", {**data, **extra}, content_type="application/json")
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def test_multiple_turns_keep_context_and_continue_collecting_other_attributes(self):
        first = self.post("macho com tosse")
        self.assertEqual(first["pergunta_complementar"]["campo"], "temperatura_corporal_c")
        second = self.post("40,2", first)
        self.assertEqual(second["variaveis_reconhecidas"]["temperatura_corporal_c"], 40.2)
        self.assertEqual(second["pergunta_complementar"]["campo"], "idade_dias")
        third = self.post("2 meses", second)
        self.assertEqual(third["variaveis_reconhecidas"]["idade_dias"], 60)
        fourth = self.post("está na creche", third)
        self.assertEqual(fourth["variaveis_reconhecidas"]["fase_reprodutiva"], "Creche")
        self.assertEqual(fourth["pergunta_complementar"]["campo"], "duracao_horas")
        fifth = self.post("2 dias", fourth)
        self.assertEqual(fifth["variaveis_reconhecidas"]["duracao_horas"], 48)
        sixth = self.post("32", fifth)
        self.assertEqual(sixth["variaveis_reconhecidas"]["temperatura_ambiente_c"], 32)
        self.assertEqual(sixth["variaveis_reconhecidas"]["temperatura_corporal_c"], 40.2)
        self.assertIn("Tosse", sixth["sintomas_reconhecidos"])

    def test_context_without_symptoms_is_accepted_and_acknowledged(self):
        result = self.post("temperatura ambiente 35 graus. Leitoa de 3 meses de idade")
        self.assertEqual(result["variaveis_reconhecidas"]["idade_dias"], 90)
        self.assertEqual(result["variaveis_reconhecidas"]["tipo_suino"], "Leitoa")
        self.assertEqual(result["variaveis_reconhecidas"]["temperatura_ambiente_c"], 35)
        self.assertIsNone(result["variaveis_reconhecidas"]["temperatura_corporal_c"])
        self.assertEqual(result["hipoteses"], [])
        self.assertIn("ambiente (°C): 35", result["resposta"])

    def test_structured_context_and_later_corrections(self):
        result = self.post("tosse", dados_clinicos={"temperatura_corporal_c": 40.5, "temperatura_ambiente_c": -5,
            "idade_dias": 40, "peso_kg": 12.5, "tipo_suino": "Leitoa", "animais_afetados": 3})
        values = result["variaveis_reconhecidas"]
        self.assertEqual(values["temperatura_ambiente_c"], -5)
        self.assertEqual(values["peso_kg"], 12.5)
        self.assertEqual(values["animais_afetados"], 3)
        corrected = self.post("Correção: temperatura corporal 38,5 °C; sem tosse", result)
        self.assertEqual(corrected["variaveis_reconhecidas"]["temperatura_corporal_c"], 38.5)
        self.assertNotIn("Tosse", corrected["sintomas_reconhecidos"])
        self.assertIn("Tosse", corrected["sintomas_negados"])
        self.assertNotIn("Febre", corrected["sintomas_reconhecidos"])

    def test_unknown_answer_does_not_repeat_a_question_or_invent_temperature(self):
        result = self.post("tosse")
        result = self.post("não sei", result)
        self.assertIsNone(result["variaveis_reconhecidas"]["temperatura_corporal_c"])
        self.assertNotEqual(result["pergunta_complementar"]["campo"], "temperatura_corporal_c")

    def test_short_negative_and_uncertain_answers_apply_to_asked_symptom(self):
        for answer, key in [("não", "sintomas_negados"), ("não sei", "sintomas_incertos")]:
            result = self.post(answer, contexto_clinico="tosse", pergunta_anterior={"campo": "sintoma", "sintoma": "Diarreia"})
            self.assertIn("Diarreia", result[key])
            self.assertNotIn("Diarreia", result["sintomas_reconhecidos"])

    def test_no_question_remains_conversation_open(self):
        result = self.post("tosse")
        with patch("bulario.triage.next_question", return_value=None):
            updated = self.post("Agora apresenta vômito", result)
        self.assertIn("Vômito", updated["sintomas_reconhecidos"])
        self.assertIn("Pode continuar", updated["resposta"])

    def test_medication_request_uses_same_case_and_returns_association_explanation(self):
        result = self.post("tosse e febre")
        result = self.post("quais fármacos estão relacionados?", result)
        self.assertIn("Tosse", result["sintomas_reconhecidos"])
        self.assertIn("Associações no bulário", result["resposta"])
        self.assertEqual(result["pipeline"]["farmacos"], "associacoes_relacionais")
        self.assertTrue(all("doencas_associadas" in item for item in result["farmacos_relacionados"]))

    def test_extraction_happens_once_in_comparison(self):
        with patch("bulario.triage.extract_clinical_case", wraps=extract_clinical_case) as extractor:
            response = self.client.post("/api/comparacao-inferencia/", {"texto": "tosse"}, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(extractor.call_count, 1)

    def test_default_uses_supervised_naive_bayes(self):
        response = self.client.post("/api/triagem/", {"texto": "tosse"}, content_type="application/json")
        if not MotorMachineLearning.artifact_path.exists():
            self.assertEqual(response.status_code, 503)
        else:
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["mecanismo"], "machine_learning")

    def test_missing_artifact_is_explicit_instead_of_changing_default_model(self):
        with patch.object(MotorMachineLearning, "_load_artifact", return_value=None):
            response = self.client.post("/api/triagem/", {"texto": "tosse"}, content_type="application/json")
            status = self.client.get("/api/machine-learning/status/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(status.status_code, 503)
        self.assertFalse(status.json()["treinado"])

    def test_invalid_inputs_return_400(self):
        for payload in [{"texto": None}, {"texto": []}, {"texto": "tosse", "mecanismo": []},
                        {"texto": "tosse", "contexto_clinico": None}, {"texto": ""},
                        {"dados_clinicos": {"temperatura_corporal_c": 500}}, {"dados_clinicos": {"idade_dias": -1}},
                        {"texto": "tosse", "pergunta_anterior": {"campo": "outro"}}]:
            with self.subTest(payload=payload):
                response = self.client.post("/api/triagem/", payload, content_type="application/json")
                self.assertEqual(response.status_code, 400)

    def test_preparation_does_not_mutate_base_over_http(self):
        before = Doenca.objects.count()
        response = self.client.post("/api/preparacao-dados/", {"limpar": True}, content_type="application/json")
        self.assertIn(response.status_code, [401, 403])
        admin = get_user_model().objects.create_user(username="admin-test", is_staff=True)
        client = APIClient()
        client.force_authenticate(user=admin)
        self.assertEqual(client.post("/api/preparacao-dados/", {"limpar": True}, format="json").status_code, 405)
        self.assertEqual(Doenca.objects.count(), before)

    def test_catalog_comes_from_database(self):
        medication = Farmaco.objects.create(nome_comercial="Novo registro da API")
        response = self.client.get("/api/catalogo/")
        self.assertIn(medication.id, [item["id"] for item in response.json()["farmacos"]])


class ArchitectureRegressionTests(TestCase):
    def test_reimport_reconciles_removed_symptom_relations(self):
        tables = {"BaseDoencas.csv": [{"DOENÇA PADRONIZADA": "Teste", "SINTOMAS PADRONIZADOS": "Tosse; Febre"}]}
        with patch("bulario.data_pipeline.read_structured_csv", side_effect=lambda path, marker: tables.get(path.name, [])):
            import_base_data(Path("unused"))
            tables["BaseDoencas.csv"][0]["SINTOMAS PADRONIZADOS"] = "Tosse"
            import_base_data(Path("unused"))
        self.assertEqual(list(Doenca.objects.get().sintomas.values_list("nome", flat=True)), ["Tosse"])

    def test_medications_follow_disease_rank_and_documented_priority(self):
        disease = Doenca.objects.create(nome="Hipótese principal")
        other = Doenca.objects.create(nome="Outra hipótese")
        for name, priority, linked in [("A", 2, disease), ("B", 1, disease), ("C", 1, other)]:
            medication = Farmaco.objects.create(nome_comercial=name)
            Indicacao.objects.create(medicamento=name, farmaco=medication, doenca=linked,
                                     doenca_indicacao=linked.nome, tipo="associacao", prioridade=priority)
        result = select_medications([{"id": disease.id}, {"id": other.id}])
        self.assertEqual([item["nome_comercial"] for item in result], ["B", "A", "C"])
        self.assertEqual(result[0]["doencas_associadas"], ["Hipótese principal"])

    def test_pig_list_query_count_stays_constant(self):
        user = get_user_model().objects.create_user(username="query-test")
        client = APIClient()
        client.force_authenticate(user=user)
        counts = []
        for number in range(1, 7):
            pig = Pig.objects.create(owner=user, name=f"Animal {number}")
            MedicationApplication.objects.create(pig=pig, medicine_name="Teste", applied_at=date(2026, 1, 1))
            if number in [1, 6]:
                with CaptureQueriesContext(connection) as captured:
                    response = client.get("/api/suinos/")
                self.assertEqual(response.status_code, 200)
                counts.append(len(captured))
        self.assertEqual(counts[0], counts[1])
