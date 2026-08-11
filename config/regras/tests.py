from django.test import TestCase

from bulario.models import Doenca, Sintoma

from .engine import MotorRegras


class MotorRegrasTests(TestCase):
    def test_ranqueia_doenca_por_cobertura_dos_sintomas(self):
        tosse = Sintoma.objects.create(nome="Tosse")
        febre = Sintoma.objects.create(nome="Febre")
        doenca = Doenca.objects.create(nome="Doença respiratória")
        doenca.sintomas.set([tosse, febre])

        resultado = MotorRegras().inferir("Animal com tosse e febre")

        self.assertEqual(resultado["hipoteses"][0]["nome"], doenca.nome)
        self.assertEqual(set(resultado["sintomas_reconhecidos"]), {"Tosse", "Febre"})

    def test_phase_and_gender_penalize_pregnancy_only_disease_for_male(self):
        febre = Sintoma.objects.create(nome="Febre")
        termination = Doenca.objects.create(nome="Doença de terminação", fase_comum="Terminação")
        pregnancy = Doenca.objects.create(nome="Doença gestacional", fase_comum="Reprodutores (gestação)")
        termination.sintomas.add(febre)
        pregnancy.sintomas.add(febre)

        result = MotorRegras().inferir("macho em terminação com febre")

        self.assertEqual(result["hipoteses"][0]["nome"], termination.nome)
        self.assertGreater(result["hipoteses"][0]["score"], result["hipoteses"][1]["score"])
