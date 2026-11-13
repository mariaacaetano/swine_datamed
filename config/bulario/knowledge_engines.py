"""Modelos experimentais: Naive Bayes, Sugeno e composição max–min de Sanchez."""
import math

from .clinical_input import extract_clinical_case
from .models import Doenca, Sintoma
from .contracts import inference_result
from .utils import normalize, clinical_symptoms, is_clinical_symptom


def _result(nome, caso, hypotheses, incluir_indicacoes=True, limite=5, **metadata):
    hypotheses.sort(key=lambda item: (-item["score"], item["nome"]))
    hypotheses = hypotheses[:max(0, limite)]
    return inference_result(caso, hypotheses, nome, incluir_indicacoes, **metadata)


class MotorBayesiano:
    """Rede em estrela D -> S_i com independência condicional (Naive Bayes).

    CPTs manuais: P(S_i=1|D)=0,8 se associado; 0,2 caso contrário.
    P(S_i=0|D) é o complemento. Todos os diagnósticos recebem a mesma
    evidência; variáveis desconhecidas/incertas são marginalizadas (fator 1).
    São parâmetros experimentais, sem estimação/calibração clínica.
    """
    nome = "rede_bayesiana"
    PROBABILIDADE_ASSOCIADO = 0.8
    PROBABILIDADE_NAO_ASSOCIADO = 0.2

    def __init__(self, p_associado=0.8, p_nao_associado=0.2):
        if not 0 < p_nao_associado < p_associado < 1:
            raise ValueError("Exige-se 0 < p_nao_associado < p_associado < 1.")
        self.PROBABILIDADE_ASSOCIADO = p_associado
        self.PROBABILIDADE_NAO_ASSOCIADO = p_nao_associado

    def inferir(self, texto, limite=5, incluir_indicacoes=True):
        return self.inferir_caso(extract_clinical_case(texto), limite, incluir_indicacoes)

    def inferir_caso(self, caso, limite=5, incluir_indicacoes=True):
        observed = {item.id for item in caso["sintomas"]}
        negative_names = {normalize(name) for name in caso["sintomas_negados"]}
        negative = {item.id for item in Sintoma.objects.all() if normalize(item.nome) in negative_names}
        diseases = [d for d in Doenca.objects.prefetch_related("sintomas") if clinical_symptoms(d)]
        hypotheses = []
        # Sem observação confirmada, a aplicação se abstém de listar priors.
        if observed:
            for disease in diseases:
                symptoms = clinical_symptoms(disease)
                ids = {item.id for item in symptoms}
                log_score = -math.log(len(diseases))
                for symptom_id in observed | negative:
                    probability = (self.PROBABILIDADE_ASSOCIADO if symptom_id in ids
                                   else self.PROBABILIDADE_NAO_ASSOCIADO)
                    log_score += math.log(1 - probability if symptom_id in negative else probability)
                hypotheses.append({"id": disease.id, "nome": disease.nome, "tipo": disease.tipo,
                                   "fase_comum": disease.fase_comum, "score_log": log_score,
                                   "evidencias": [s.nome for s in symptoms if s.id in observed]})
        if hypotheses:
            maximum = max(item["score_log"] for item in hypotheses)
            weights = [math.exp(item["score_log"] - maximum) for item in hypotheses]
            total = sum(weights)
            for item, weight in zip(hypotheses, weights):
                item["score"] = round(weight / total, 6)
                item.pop("score_log")
        return _result(self.nome, caso, hypotheses, incluir_indicacoes, limite,
                       modelo="Naive Bayes com CPTs manuais", tipo_score="posterior_modelo",
                       parametros={"p_associado": self.PROBABILIDADE_ASSOCIADO,
                                   "p_nao_associado": self.PROBABILIDADE_NAO_ASSOCIADO,
                                   "prior": "uniforme", "origem": "experimental"},
                       politica_ausencia="Sintomas desconhecidos e incertos marginalizados.",
                       calibracao_clinica=False)


def pertinencias(value):
    """Partição triangular com ombros em [0,1], centros 0, 0,5 e 1."""
    value = max(0.0, min(1.0, value))
    return {"baixo": max(0.0, 1 - 2 * value),
            "medio": max(0.0, 1 - abs(2 * value - 1)),
            "alto": max(0.0, 2 * value - 1)}


def inferir_sugeno(coverage, precision):
    """Nove regras, AND produto, consequentes constantes, média ponderada.

    SE cobertura é X E precisão é Y ENTÃO suporte = min(centro(X), centro(Y)).
    O mínimo define a tabela de consequentes, não uma composição Sanchez.
    """
    centers = {"baixo": 0.0, "medio": 0.5, "alto": 1.0}
    rules = []
    for cover_label, cover_degree in pertinencias(coverage).items():
        for precision_label, precision_degree in pertinencias(precision).items():
            activation = cover_degree * precision_degree
            if activation > 0:
                rules.append({"regra": f"cobertura_{cover_label}_precisao_{precision_label}",
                              "ativacao": activation,
                              "consequente": min(centers[cover_label], centers[precision_label])})
    total = sum(rule["ativacao"] for rule in rules)
    score = sum(rule["ativacao"] * rule["consequente"] for rule in rules) / total if total else 0.0
    return score, rules


def graus_observados(caso, peso_incerto=0.5):
    """Pesos experimentais da observação, compartilhados pelos dois motores fuzzy."""
    observed = {item.id for item in caso["sintomas"]}
    uncertain = {normalize(item) for item in caso["sintomas_incertos"]}
    temperature = caso["variaveis"].get("temperatura_corporal_c")
    degrees = {}
    for symptom in Sintoma.objects.all():
        if not is_clinical_symptom(symptom.nome):
            continue
        name = normalize(symptom.nome)
        if symptom.id in observed:
            degree = 1.0
            if temperature is not None and name in {"febre", "febre alta"}:
                threshold = 40.0 if name == "febre alta" else 39.5
                degree = max(0.0, min(1.0, (temperature - threshold) / 0.5))
            degrees[symptom.id] = degree
        elif name in uncertain:
            degrees[symptom.id] = peso_incerto
    return degrees


def composicao_max_min(observations, relation):
    """(P ∘ R)(d) = max_s min(P(s), R(s,d)); ausência de ligação vale zero."""
    if any(not 0 <= value <= 1 for value in [*observations.values(), *relation.values()]):
        raise ValueError("Graus da composição devem pertencer a [0, 1].")
    terms = {key: min(value, relation.get(key, 0.0)) for key, value in observations.items()}
    return max(terms.values(), default=0.0), terms


class MotorFuzzySanchez:
    """Composição paciente–sintoma ∘ sintoma–doença, sem média ou desempate heurístico.

    A base registra vínculos, sem graus clínicos: R=1 para vínculos cadastrados
    e R=0 para os demais. Essa relação binária é um caso particular fuzzy;
    o máximo produz empates esperados, expostos ao usuário.
    """
    nome = "fuzzy_sanchez"

    def inferir(self, texto, limite=5, incluir_indicacoes=True):
        return self.inferir_caso(extract_clinical_case(texto), limite, incluir_indicacoes)

    def inferir_caso(self, caso, limite=5, incluir_indicacoes=True):
        degrees = graus_observados(caso)
        hypotheses = []
        for disease in Doenca.objects.prefetch_related("sintomas"):
            symptoms = clinical_symptoms(disease)
            relation = {item.id: 1.0 for item in symptoms}
            score, terms = composicao_max_min(degrees, relation)
            if score <= 0:
                continue
            hypotheses.append({"id": disease.id, "nome": disease.nome, "tipo": disease.tipo,
                               "fase_comum": disease.fase_comum, "score": round(score, 6),
                               "grau_pertinencia": round(score, 6),
                               "evidencias": [s.nome for s in symptoms if terms.get(s.id, 0) > 0],
                               "composicao": [{"sintoma": s.nome, "grau_observado": degrees.get(s.id, 0),
                                               "grau_relacao": 1.0, "minimo": terms.get(s.id, 0)}
                                              for s in symptoms if s.id in degrees]})
        best = max((item["score"] for item in hypotheses), default=0)
        return _result(self.nome, caso, hypotheses, incluir_indicacoes, limite,
                       modelo="Sanchez — composição max–min", tipo_score="composicao_max_min",
                       relacao="Binária: vínculo cadastrado=1; vínculo não cadastrado=0.",
                       parametros={"peso_incerto": 0.5, "origem_peso": "experimental"},
                       empates_no_maior_grau=sum(item["score"] == best for item in hypotheses),
                       politica_ausencia="Negados e desconhecidos não fornecem suporte positivo.",
                       calibracao_clinica=False)


class MotorFuzzy:
    """Sugeno de ordem zero sobre cobertura e precisão graduadas.

    A certeza da observação (1 confirmada, 0,5 incerta) é um peso experimental,
    distinto da pertinência nos conjuntos linguísticos baixo/médio/alto.
    """
    nome = "fuzzy"
    PESO_OBSERVACAO_INCERTA = 0.5

    def inferir(self, texto, limite=5, incluir_indicacoes=True):
        return self.inferir_caso(extract_clinical_case(texto), limite, incluir_indicacoes)

    def inferir_caso(self, caso, limite=5, incluir_indicacoes=True):
        observed = {item.id for item in caso["sintomas"]}
        uncertain = {normalize(item) for item in caso["sintomas_incertos"]}
        degrees = graus_observados(caso, self.PESO_OBSERVACAO_INCERTA)
        total_observed = sum(degrees.values())
        hypotheses = []
        for disease in Doenca.objects.prefetch_related("sintomas"):
            symptoms = clinical_symptoms(disease)
            support = sum(degrees.get(s.id, 0) for s in symptoms)
            if not symptoms or support <= 0 or total_observed <= 0:
                continue
            coverage, precision = support / len(symptoms), support / total_observed
            score, rules = inferir_sugeno(coverage, precision)
            if score <= 0:
                continue
            hypotheses.append({"id": disease.id, "nome": disease.nome, "tipo": disease.tipo,
                               "fase_comum": disease.fase_comum, "score": round(score, 6),
                               "grau_pertinencia": round(score, 6),
                               "entradas_fuzzy": {"cobertura": coverage, "precisao": precision},
                               "regras_fuzzy": rules,
                               "evidencias": [s.nome for s in symptoms if s.id in observed],
                               "evidencias_incertas": [s.nome for s in symptoms if normalize(s.nome) in uncertain]})
        return _result(self.nome, caso, hypotheses, incluir_indicacoes, limite,
                       modelo="Sugeno de ordem zero", tipo_score="suporte_fuzzy",
                       politica_ausencia="Sintomas desconhecidos não afirmados; cobertura refere-se ao perfil cadastrado.",
                       calibracao_clinica=False)
