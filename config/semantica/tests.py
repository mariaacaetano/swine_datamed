from django.test import TestCase

from bulario.models import Doenca, Sintoma

from .engine import MotorSemantico


class MotorSemanticoTests(TestCase):
    def test_expoe_aresta_que_fundamenta_a_hipotese(self):
        diarreia = Sintoma.objects.create(nome="Diarreia")
        doenca = Doenca.objects.create(nome="Enteropatia")
        doenca.sintomas.add(diarreia)

        resultado = MotorSemantico().inferir("Foi observada diarreia")

        self.assertEqual(resultado["hipoteses"][0]["arestas_semanticas"], ["Diarreia -> Enteropatia"])
        self.assertEqual(resultado["hipoteses"][0]["caminhos_semanticos"],
                         resultado["hipoteses"][0]["arestas_semanticas"])

    def test_jaccard_usa_uniao_dos_sintomas_e_descarta_sem_correspondencia(self):
        diarreia = Sintoma.objects.create(nome="Diarreia")
        febre = Sintoma.objects.create(nome="Febre")
        tosse = Sintoma.objects.create(nome="Tosse")
        candidata = Doenca.objects.create(nome="Candidata")
        candidata.sintomas.set([diarreia, tosse])
        outra = Doenca.objects.create(nome="Sem correspondência")
        outra.sintomas.add(tosse)
        resultado = MotorSemantico().inferir("diarreia e febre")
        self.assertEqual(len(resultado["hipoteses"]), 1)
        self.assertEqual(resultado["hipoteses"][0]["id"], candidata.id)
        self.assertAlmostEqual(resultado["hipoteses"][0]["score"], 1 / 3, places=6)

    def test_sem_sintomas_nao_calcula_divisao(self):
        self.assertEqual(MotorSemantico().inferir("")["hipoteses"], [])
