from unittest.mock import Mock, patch

from django.test import TestCase

from .medications import select_medications
from .models import Doenca, Farmaco, Indicacao, Vacina
from .triage import run_engine
from .tests_support import complete_medication_data


class MedicationRetrievalTests(TestCase):
    def setUp(self):
        self.first = Doenca.objects.create(nome="Primeira hipótese")
        self.second = Doenca.objects.create(nome="Segunda hipótese")

    def indication(self, name, disease=None, priority=None):
        medication, _ = Farmaco.objects.get_or_create(nome_comercial=name,
            defaults={key: value for key, value in complete_medication_data().items() if key != "nome_comercial"})
        Indicacao.objects.create(medicamento=name, farmaco=medication,
            doenca=disease or self.first, doenca_indicacao=(disease or self.first).nome,
            tipo="associacao", prioridade=priority)
        return medication

    def test_empty_hypotheses_do_not_return_products(self):
        self.indication("Produto cadastrado")
        self.assertEqual(select_medications([]), [])

    def test_no_relationship_does_not_generate_medication_from_disease_name(self):
        Farmaco.objects.create(nome_comercial=self.first.nome, indicacoes_principais=self.first.nome)
        self.assertEqual(select_medications([{"id": self.first.id}]), [])

    def test_disease_order_precedes_indication_priority(self):
        first = self.indication("Primeiro", priority=5)
        second = self.indication("Segundo", self.second, priority=1)
        result = select_medications([{"id": self.first.id}, {"id": self.second.id}])
        self.assertEqual([item["id"] for item in result], [first.id, second.id])

    def test_priority_then_name_are_deterministic_and_output_is_limited(self):
        for name, priority in [("Z", None), ("C", 2), ("B", 1), ("A", 1)]:
            self.indication(name, priority=priority)
        hypotheses = [{"id": self.first.id}]
        self.assertEqual([item["nome_comercial"] for item in select_medications(hypotheses)], ["A", "B", "C"])
        self.assertEqual([item["nome_comercial"] for item in select_medications(hypotheses, limit=4)], ["A", "B", "C", "Z"])

    def test_product_shared_by_diseases_is_unique_and_keeps_both_sources(self):
        medication = self.indication("Compartilhado", priority=2)
        self.indication("Compartilhado", self.second, priority=1)
        medication.doencas_relacionadas.add(self.first, self.second)
        result = select_medications([{"id": self.first.id}, {"id": self.second.id}])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], medication.id)
        self.assertCountEqual(result[0]["doencas_associadas"], [self.first.nome, self.second.nome])
        self.assertEqual(len(result[0]["evidencias_associacao"]), 2)

    def test_direct_relationship_is_available_without_indication_row(self):
        medication = Farmaco.objects.create(**complete_medication_data(nome_comercial="Vínculo direto"))
        medication.doencas_relacionadas.add(self.first)
        result = select_medications([{"id": self.first.id}])
        self.assertEqual([item["id"] for item in result], [medication.id])
        self.assertEqual(result[0]["evidencias_associacao"], [])
        self.assertIsNone(result[0]["prioridade_base"])

    def test_vaccines_are_not_returned_as_therapeutic_drugs(self):
        vaccine = Vacina.objects.create(nome_comercial="Vacina preventiva")
        Indicacao.objects.create(medicamento=vaccine.nome_comercial, vacina=vaccine,
            doenca=self.first, doenca_indicacao=self.first.nome, tipo="prevencao", prioridade=1)
        self.assertEqual(select_medications([{"id": self.first.id}]), [])

    def test_metadata_is_preserved_without_computing_dosage(self):
        medication = self.indication("Metadados", priority=1)
        medication.principio_ativo = "Princípio cadastrado"
        medication.carencia = "Conforme a bula de origem"
        medication.contraindicacoes = "Restrições da fonte"
        medication.save()
        result = select_medications([{"id": self.first.id}])[0]
        self.assertEqual(result["principio_ativo"], medication.principio_ativo)
        self.assertEqual(result["carencia"], medication.carencia)
        self.assertEqual(result["contraindicacoes"], medication.contraindicacoes)
        self.assertNotIn("dose_calculada", result)

    def test_pipeline_queries_bulario_after_classification(self):
        medication = self.indication("Produto associado", priority=1)
        motor = Mock(spec=["inferir_caso"])
        motor.inferir_caso.return_value = {"mecanismo": "regras", "hipoteses": [{"id": self.first.id}],
            "sintomas_reconhecidos": ["Tosse"], "sintomas_incertos": []}
        definition = Mock()
        definition.engine.return_value = motor
        case = {"entrada": "tosse"}
        with patch("bulario.triage.engine_registry", return_value={"regras": definition}):
            result = run_engine(case, "regras")
        motor.inferir_caso.assert_called_once_with(case, incluir_indicacoes=False)
        self.assertEqual([item["id"] for item in result["farmacos_relacionados"]], [medication.id])
        self.assertEqual(result["hipoteses"][0]["id"], self.first.id)
