"""Encadeamento progressivo monotônico sobre fatos simbólicos por enfermidade."""
from dataclasses import dataclass
from typing import Callable

from bulario.clinical_input import extract_clinical_case
from bulario.models import Doenca
from bulario.utils import normalize, clinical_symptoms
from .engine import MotorRegras


@dataclass(frozen=True)
class Regra:
    nome: str
    condicao: Callable
    consequencia: Callable


def encadear(fatos, regras):
    """Dispara cada regra uma vez, em rodadas, até atingir ponto fixo."""
    memoria = set(fatos)
    disparadas = set()
    trilha = []
    rodada = 0
    while True:
        rodada += 1
        anteriores = frozenset(memoria)
        novos = set()
        for regra in regras:
            if regra.nome not in disparadas and regra.condicao(anteriores):
                derivados = set(regra.consequencia(anteriores)) - memoria
                novos.update(derivados)
                disparadas.add(regra.nome)
                trilha.append({"regra": regra.nome, "rodada": rodada,
                               "premissas": sorted(anteriores), "fatos_derivados": sorted(derivados)})
        if not novos:
            return memoria, trilha
        memoria.update(novos)


class MotorRegrasEncadeadas(MotorRegras):
    """Deriva candidatas, admissibilidade, suporte e hipóteses por regras.

    As categorias de suporte são ordinais, sem probabilidade ou soma de pesos.
    As regras são escolhas explícitas de implementação, não validação clínica.
    """
    nome = "regras_encadeadas"

    def inferir(self, texto, limite=5, incluir_indicacoes=True):
        return self.inferir_caso(extract_clinical_case(texto), limite, incluir_indicacoes)

    def inferir_caso(self, caso, limite=5, incluir_indicacoes=True):
        presentes = {item.id for item in caso["sintomas"]}
        negados = {normalize(item) for item in caso["sintomas_negados"]}
        hipoteses, rastros = [], []
        for doenca in Doenca.objects.prefetch_related("sintomas"):
            sintomas = clinical_symptoms(doenca)
            evidencias = [s for s in sintomas if s.id in presentes]
            fatos = set()
            if evidencias:
                fatos.add("evidencia_positiva")
            if sintomas and all(s.id in presentes for s in sintomas):
                fatos.add("todos_sintomas_presentes")
            if any(normalize(s.nome) in negados for s in sintomas):
                fatos.add("sintoma_associado_negado")
            fase = normalize(doenca.fase_comum)
            variaveis = caso["variaveis"]
            if ("gestacao" in fase or "gestante" in fase) and variaveis["genero"].startswith("Macho"):
                fatos.add("restricao_reprodutiva")
            fase_caso = normalize(variaveis["fase_reprodutiva"])
            if (fase_caso and fase and "nao informado" not in fase
                    and "todas as fases" not in fase and fase_caso not in fase
                    and not (fase_caso == "terminacao" and "crescimento" in fase)):
                fatos.add("fase_divergente")
            regras = [
                Regra("E1_SELECAO", lambda f: "evidencia_positiva" in f, lambda f: {"candidata"}),
                # Associação não estabelece um sintoma obrigatório. Uma
                # negação impede suporte completo, mas não exclui a doença.
                Regra("E2_BLOQUEIO", lambda f: "candidata" in f and "restricao_reprodutiva" in f, lambda f: {"bloqueada"}),
                Regra("E3_ADMISSAO", lambda f: "candidata" in f and "restricao_reprodutiva" not in f, lambda f: {"admissivel"}),
                Regra("E4_SUPORTE_COMPLETO", lambda f: {"admissivel", "todos_sintomas_presentes"} <= f, lambda f: {"suporte_completo"}),
                Regra("E5_SUPORTE_PARCIAL", lambda f: "admissivel" in f and "todos_sintomas_presentes" not in f, lambda f: {"suporte_parcial"}),
                Regra("E6_HIPOTESE_COMPLETA", lambda f: "suporte_completo" in f and "fase_divergente" not in f, lambda f: {"hipotese_completa"}),
                Regra("E7_HIPOTESE_PARCIAL", lambda f: "suporte_parcial" in f and "fase_divergente" not in f, lambda f: {"hipotese_parcial"}),
                Regra("E8_HIPOTESE_RESTRITA", lambda f: bool(f & {"suporte_completo", "suporte_parcial"}) and "fase_divergente" in f, lambda f: {"hipotese_com_restricao_de_fase"}),
            ]
            memoria, trilha = encadear(fatos, regras)
            if trilha:
                rastros.append({"doenca_id": doenca.id, "fatos_iniciais": sorted(fatos),
                                "fatos_finais": sorted(memoria), "disparos": trilha})
            categorias = [("hipotese_completa", 1.0), ("hipotese_parcial", 0.5),
                          ("hipotese_com_restricao_de_fase", 0.25)]
            for categoria, ordem in categorias:
                if categoria in memoria:
                    item = self._hipotese(doenca, ordem, evidencias)
                    item.update({"categoria_suporte": categoria, "regras_disparadas": trilha})
                    hipoteses.append(item)
                    break
        hipoteses.sort(key=lambda item: (-item["score"], item["nome"]))
        resultado = self._resultado(caso, hipoteses[:max(0, limite)], incluir_indicacoes)
        resultado.update({"tipo_score": "ordinal", "trilha_inferencia": rastros})
        return resultado
