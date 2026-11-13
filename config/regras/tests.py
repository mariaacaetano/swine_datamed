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


class MotorEncadeadoTests(TestCase):
    def setUp(self):
        from .chaining import MotorRegrasEncadeadas
        self.motor = MotorRegrasEncadeadas()
        self.tosse = Sintoma.objects.create(nome="Tosse")
        self.febre = Sintoma.objects.create(nome="Febre")
        self.doenca = Doenca.objects.create(nome="Respiratória")
        self.doenca.sintomas.set([self.tosse, self.febre])

    def test_derivacao_em_quatro_rodadas_com_evidencias(self):
        resultado = self.motor.inferir("tosse e febre")
        h = resultado["hipoteses"][0]
        self.assertEqual(h["categoria_suporte"], "hipotese_completa")
        self.assertEqual([r["rodada"] for r in h["regras_disparadas"]], [1, 2, 3, 4])
        self.assertEqual([r["regra"] for r in h["regras_disparadas"]],
                         ["E1_SELECAO", "E3_ADMISSAO", "E4_SUPORTE_COMPLETO", "E6_HIPOTESE_COMPLETA"])
        self.assertEqual(set(h["evidencias"]), {"Tosse", "Febre"})
        self.assertEqual(resultado["tipo_score"], "ordinal")

    def test_sintoma_associado_negado_nao_e_criterio_de_exclusao(self):
        resultado = self.motor.inferir("tosse, não apresenta febre")
        self.assertEqual(resultado["hipoteses"][0]["categoria_suporte"], "hipotese_parcial")
        self.assertIn("sintoma_associado_negado", resultado["trilha_inferencia"][0]["fatos_iniciais"])
        self.assertNotIn("bloqueada", resultado["trilha_inferencia"][0]["fatos_finais"])

    def test_sintomas_incertos_nao_geram_suporte_completo(self):
        self.assertEqual(self.motor.inferir("talvez tosse e febre")["hipoteses"], [])
        result = self.motor.inferir("tosse. Talvez febre")
        self.assertEqual(result["hipoteses"][0]["categoria_suporte"], "hipotese_parcial")

    def test_sintoma_nao_mencionado_nao_e_negacao(self):
        h = self.motor.inferir("tosse")["hipoteses"][0]
        self.assertEqual(h["categoria_suporte"], "hipotese_parcial")

    def test_restricao_reprodutiva_bloqueia(self):
        self.doenca.fase_comum = "Gestação"
        self.doenca.save()
        self.assertEqual(self.motor.inferir("macho com tosse e febre")["hipoteses"], [])

    def test_fase_divergente_deriva_hipotese_restrita(self):
        self.doenca.fase_comum = "Creche"
        self.doenca.save()
        h = self.motor.inferir("em terminação com tosse e febre")["hipoteses"][0]
        self.assertEqual(h["categoria_suporte"], "hipotese_com_restricao_de_fase")

    def test_sem_evidencias_nao_gera_candidatas(self):
        self.assertEqual(self.motor.inferir("animal saudável")["hipoteses"], [])

    def test_ponto_fixo_independe_da_ordem_e_nao_repete_regra(self):
        from .chaining import Regra, encadear
        regras = [Regra("segunda", lambda f: "b" in f, lambda f: {"c"}),
                  Regra("primeira", lambda f: "a" in f, lambda f: {"b"}),
                  Regra("ciclo", lambda f: "c" in f, lambda f: {"a"})]
        fatos, trilha = encadear({"a"}, regras)
        self.assertEqual(fatos, {"a", "b", "c"})
        self.assertEqual(len(trilha), 3)
        self.assertEqual([r["rodada"] for r in trilha], [1, 2, 3])

    def test_endpoint_e_triagem_aceitam_motor_encadeado(self):
        for url, dados in [("/api/regras/encadeadas/inferir/", {"texto": "tosse"}),
                           ("/api/triagem/", {"texto": "tosse", "mecanismo": "regras_encadeadas"})]:
            resposta = self.client.post(url, dados, content_type="application/json")
            self.assertEqual(resposta.status_code, 200)
            self.assertEqual(resposta.json()["mecanismo"], "regras_encadeadas")
