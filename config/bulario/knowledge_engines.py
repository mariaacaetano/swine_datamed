import math

from .clinical_input import extract_clinical_case
from .models import Doenca, Farmaco


def _result(nome, caso, hypotheses):
    hypotheses.sort(key=lambda item: (-item["score"], item["nome"]))
    hypotheses = hypotheses[:5]
    ids = [item["id"] for item in hypotheses]
    farmacos = Farmaco.objects.filter(doencas_relacionadas__id__in=ids).distinct()[:3]
    return {
        "mecanismo": nome,
        "sintomas_reconhecidos": [item.nome for item in caso["sintomas"]],
        "sintomas_negados": caso["sintomas_negados"],
        "sintomas_incertos": caso["sintomas_incertos"],
        "variaveis_reconhecidas": caso["variaveis"],
        "alertas": caso["alertas"],
        "hipoteses": hypotheses,
        "farmacos_relacionados": [{
            "nome_comercial": item.nome_comercial,
            "principio_ativo": item.principio_ativo,
            "via_administracao": item.via_administracao,
            "carencia": item.carencia,
        } for item in farmacos],
    }


class MotorBayesiano:
    nome = "rede_bayesiana"

    def inferir(self, texto, limite=5):
        caso = extract_clinical_case(texto)
        observados = {item.id for item in caso["sintomas"]}
        negados = {item.lower() for item in caso["sintomas_negados"]}
        doencas = list(Doenca.objects.prefetch_related("sintomas").all())
        hypotheses = []
        prior = 1 / max(len(doencas), 1)
        for disease in doencas:
            symptoms = list(disease.sintomas.all())
            if not symptoms:
                continue
            log_score = math.log(prior)
            for symptom in symptoms:
                likelihood = 0.80 if symptom.id in observados else 0.20
                if symptom.nome.lower() in negados:
                    likelihood = 0.03
                log_score += math.log(likelihood)
            hypotheses.append({"id": disease.id, "nome": disease.nome, "tipo": disease.tipo,
                               "fase_comum": disease.fase_comum, "score_log": log_score,
                               "evidencias": [s.nome for s in symptoms if s.id in observados]})
        if hypotheses:
            maximum = max(item["score_log"] for item in hypotheses)
            weights = [math.exp(item["score_log"] - maximum) for item in hypotheses]
            total = sum(weights)
            for item, weight in zip(hypotheses, weights):
                item["score"] = round(weight / total, 6)
                item.pop("score_log")
        return _result(self.nome, caso, hypotheses)


class MotorFuzzy:
    nome = "fuzzy"

    def inferir(self, texto, limite=5):
        caso = extract_clinical_case(texto)
        observed = {item.id for item in caso["sintomas"]}
        uncertain = {item.lower() for item in caso["sintomas_incertos"]}
        temperature = caso["variaveis"].get("classificacao_temperatura")
        hypotheses = []
        for disease in Doenca.objects.prefetch_related("sintomas").all():
            symptoms = list(disease.sintomas.all())
            if not symptoms:
                continue
            memberships = []
            for symptom in symptoms:
                value = 1.0 if symptom.id in observed else 0.0
                if symptom.nome.lower() in uncertain:
                    value = 0.5
                memberships.append(value)
            score = sum(memberships) / len(memberships)
            if temperature in {"febre", "febre alta"} and "febre" in disease.sintomas_texto.lower():
                score = min(1.0, score + 0.15)
            hypotheses.append({"id": disease.id, "nome": disease.nome, "tipo": disease.tipo,
                               "fase_comum": disease.fase_comum, "score": round(score, 6),
                               "grau_pertinencia": round(score, 6),
                               "evidencias": [s.nome for s in symptoms if s.id in observed]})
        return _result(self.nome, caso, hypotheses)
