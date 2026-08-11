from django.test import TestCase

from bulario.models import Doenca, Sintoma

from .engine import MotorSemantico


class MotorSemanticoTests(TestCase):
    def test_expoe_caminho_que_fundamenta_a_hipotese(self):
        diarreia = Sintoma.objects.create(nome="Diarreia")
        doenca = Doenca.objects.create(nome="Enteropatia")
        doenca.sintomas.add(diarreia)

        resultado = MotorSemantico().inferir("Foi observada diarreia")

        self.assertEqual(resultado["hipoteses"][0]["caminhos_semanticos"], ["Diarreia -> Enteropatia"])
