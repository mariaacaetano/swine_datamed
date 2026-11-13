from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase

from .contracts import inference_result
from .data_pipeline import import_base_data
from .medication_quality import MEDICATION_FIELDS, MISSING_VALUES, audit_medication_rows, missing_medication_fields
from .medications import select_medications
from .models import Doenca, Farmaco, Indicacao, Sintoma
from .tests_support import complete_medication_data


class MedicationCompletenessRuleTests(SimpleTestCase):
    def test_each_field_of_the_record_is_required(self):
        data = complete_medication_data()
        self.assertEqual(missing_medication_fields(data), [])
        for field in MEDICATION_FIELDS:
            with self.subTest(field=field):
                self.assertEqual(missing_medication_fields({**data, field: ""}), [field])

    def test_unknown_values_are_missing_but_documented_absence_is_valid(self):
        for value in [None, " \t\n", " COMPLETAR. ", "--", "——", *MISSING_VALUES]:
            with self.subTest(value=value):
                data = complete_medication_data(contraindicacoes=value)
                self.assertEqual(missing_medication_fields(data), ["contraindicacoes"])
        self.assertEqual(missing_medication_fields(complete_medication_data(
            contraindicacoes="Não apresenta", reacoes_adversas="Não se aplica", carencia="0 dias")), [])

    def test_source_identifier_and_external_link_are_optional(self):
        row = {column: complete_medication_data()[field] for field, column in MEDICATION_FIELDS.items()}
        self.assertEqual(missing_medication_fields(row, csv_row=True), [])
        report = audit_medication_rows([row, {**row, "Posologia": "Completar"}])
        self.assertEqual(report["total_aprovados"], 1)
        self.assertEqual(report["total_bloqueados"], 1)
        self.assertEqual(report["bloqueados"][0]["campos_ausentes"], ["Posologia"])


class MedicationPublicationTests(TestCase):
    def setUp(self):
        self.disease = Doenca.objects.create(nome="Enfermidade de teste")
        symptom = Sintoma.objects.create(nome="Tosse")
        self.disease.sintomas.add(symptom)
        self.approved = Farmaco.objects.create(**complete_medication_data(nome_comercial="Produto aprovado"))
        self.blocked = Farmaco.objects.create(**complete_medication_data(
            nome_comercial="Produto incompleto", contraindicacoes="Completar"))
        for medication in [self.approved, self.blocked]:
            medication.doencas_relacionadas.add(self.disease)
            Indicacao.objects.create(medicamento=medication.nome_comercial, farmaco=medication,
                doenca=self.disease, doenca_indicacao=self.disease.nome, tipo="Tratamento", prioridade=1)

    def test_queryset_and_importation_use_the_same_missing_value_rule(self):
        for index, value in enumerate(["\t\n", " COMPLETAR. ", "--", "——", *MISSING_VALUES]):
            Farmaco.objects.create(**complete_medication_data(nome_comercial=f"Ausente {index}", precaucoes=value))
        for field in MEDICATION_FIELDS:
            data = complete_medication_data(nome_comercial=f"Sem {field}")
            data[field] = ""
            Farmaco.objects.create(**data)
        self.assertEqual(list(Farmaco.objects.completos().values_list("id", flat=True)), [self.approved.id])

    def test_admin_model_validation_rejects_missing_fields(self):
        self.approved.full_clean()
        with self.assertRaises(ValidationError) as error:
            self.blocked.full_clean()
        self.assertIn("contraindicacoes", error.exception.message_dict)

    def test_listing_search_and_catalog_never_publish_legacy_incomplete_records(self):
        listing = self.client.get("/api/farmacos/")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual([item["id"] for item in listing.json()], [self.approved.id])
        search = self.client.get("/api/farmacos/buscar/", {"q": "Produto"})
        self.assertEqual([item["id"] for item in search.json()["results"]], [self.approved.id])
        catalog = self.client.get("/api/catalogo/")
        self.assertEqual([item["id"] for item in catalog.json()["farmacos"]], [self.approved.id])
        self.assertEqual(self.client.get("/api/preparacao-dados/").json()["base"]["farmacos"], 1)

    def test_direct_access_to_incomplete_record_returns_404(self):
        self.assertEqual(self.client.get(f"/api/farmacos/{self.blocked.id}/").status_code, 404)
        self.assertEqual(self.client.get(f"/api/farmacos/{self.approved.id}/").status_code, 200)

    def test_indications_and_direct_links_cannot_bypass_the_rule(self):
        hypotheses = [{"id": self.disease.id}]
        self.assertEqual([item["id"] for item in select_medications(hypotheses)], [self.approved.id])
        Indicacao.objects.all().delete()
        self.assertEqual([item["id"] for item in select_medications(hypotheses)], [self.approved.id])

    def test_legacy_engine_contract_filters_before_limiting_results(self):
        expected = {self.approved.nome_comercial}
        for index in range(2):
            medication = Farmaco.objects.create(**complete_medication_data(nome_comercial=f"Produto aprovado {index}"))
            medication.doencas_relacionadas.add(self.disease)
            expected.add(medication.nome_comercial)
        for index in range(3):
            incomplete = Farmaco.objects.create(nome_comercial=f"A incompleto {index}")
            incomplete.doencas_relacionadas.add(self.disease)
        case = {"sintomas": [], "sintomas_negados": [], "sintomas_incertos": [], "variaveis": {}, "alertas": []}
        result = inference_result(case, [{"id": self.disease.id}], "regras")
        self.assertEqual({item["nome_comercial"] for item in result["farmacos_relacionados"]}, expected)

    def test_triage_does_not_return_incomplete_medication(self):
        result = self.client.post("/api/triagem/", {"texto": "tosse", "mecanismo": "regras"}, content_type="application/json")
        self.assertEqual(result.status_code, 200)
        self.assertEqual([item["id"] for item in result.json()["farmacos_relacionados"]], [self.approved.id])


class MedicationImportQualityTests(TestCase):
    def setUp(self):
        data = complete_medication_data(nome_comercial="Produto da fonte")
        self.row = {column: data[field] for field, column in MEDICATION_FIELDS.items()}
        self.row["ID"] = "1"
        self.tables = {
            "BaseDoencas.csv": [{"DOENÇA PADRONIZADA": "Teste", "SINTOMAS PADRONIZADOS": "Tosse"}],
            "BularioFarmacos.csv": [self.row],
            "FarmacoDoenca.csv": [{"MEDICAMENTO": "Produto da fonte", "DOENÇA/INDICAÇÃO PADRONIZADA": "Teste", "TIPO": "Tratamento"}],
        }

    def import_source(self):
        with patch("bulario.data_pipeline.read_structured_csv", side_effect=lambda path, marker: self.tables.get(path.name, [])):
            return import_base_data("unused")

    def test_import_rejects_incomplete_rows_without_synthesizing_missing_content(self):
        self.tables["BularioFarmacos.csv"].append({**self.row, "Nome comercial": "Incompleto", "Posologia": ""})
        self.assertEqual(self.import_source()["farmacos"], 1)
        self.assertEqual(list(Farmaco.objects.values_list("nome_comercial", flat=True)), ["Produto da fonte"])

    def test_reimport_removes_stale_approved_record_when_source_becomes_incomplete(self):
        self.import_source()
        self.row["Contraindicações"] = "Não informado"
        self.assertEqual(self.import_source()["farmacos"], 0)
        self.assertFalse(Farmaco.objects.exists())
        self.assertIsNone(Indicacao.objects.get().farmaco_id)

    def test_reimport_removes_legacy_partial_records_and_recovers_completed_source(self):
        Farmaco.objects.create(nome_comercial="Importado antes da regra")
        self.assertEqual(self.import_source()["farmacos"], 1)
        self.assertFalse(Farmaco.objects.filter(nome_comercial="Importado antes da regra").exists())
        self.row["Precauções"] = "Completar"
        self.assertEqual(self.import_source()["farmacos"], 0)
        self.row["Precauções"] = "Precaução documentada"
        self.assertEqual(self.import_source()["farmacos"], 1)
