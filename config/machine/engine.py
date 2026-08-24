import math
import re
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from django.conf import settings
from bulario.clinical_input import context_adjustment, extract_clinical_case, negative_evidence_adjustment
from bulario.models import Doenca, Farmaco, Sintoma
from bulario.utils import normalize


class MotorMachineLearning:
    """Usa o artefato selecionado em validação; mantém fallback analítico explícito."""

    nome = "machine_learning"
    artifact_path = Path(settings.BASE_DIR) / "machine" / "artifacts" / "model.joblib"
    _artifact = None
    _artifact_mtime = None

    def inferir(self, texto, limite=5):
        caso = extract_clinical_case(texto)
        artifact = self._load_artifact()
        if artifact is not None:
            return self._infer_trained(caso, artifact, limite)
        return self._infer_analytical(caso, limite)

    @classmethod
    def _load_artifact(cls):
        if not cls.artifact_path.exists():
            return None
        mtime = cls.artifact_path.stat().st_mtime
        if cls._artifact is None or cls._artifact_mtime != mtime:
            cls._artifact = joblib.load(cls.artifact_path)
            cls._artifact_mtime = mtime
        return cls._artifact

    def _infer_trained(self, caso, artifact, limite):
        row = {name: 0 if name.startswith("sintoma_") else "Não informado"
               for name in artifact["feature_columns"]}
        for symptom in caso["sintomas"]:
            suffix = re.sub(r"[^a-z0-9]+", "_", normalize(symptom.nome)).strip("_")
            column = next((name for name in artifact["symptom_columns"] if name.endswith(f"_{suffix}")), None)
            if column:
                row[column] = 1
        variables = caso["variaveis"]
        temperature = variables["classificacao_temperatura"]
        temperature_values = {
            "hipotermia": "<37,0 (hipotermia)", "normal": "37,0–39,5 (normal)",
            "febre": "39,6–40,0 (febre)", "febre alta": ">40,0 (febre alta)",
        }
        values = {
            "Temperatura corporal (°C)": temperature_values.get(temperature, "Não informado"),
            "Idade": ">180 dias" if variables["idade_categoria"] == "Adulto" else "Não informado",
            "Gênero": variables["genero"] or "Não informado",
            "Fase reprodutiva": variables["fase_reprodutiva"] or "Não informado",
            "Estado reprodutivo": variables["estado_reprodutivo"] or "Não informado",
            "Duração dos sintomas": variables["duracao_categoria"] or "Não informado",
        }
        row.update({name: value for name, value in values.items() if name in row})
        frame = pd.DataFrame([row], columns=artifact["feature_columns"])
        matrix = artifact["preprocessor"].transform(frame)
        model = artifact["model"]
        if hasattr(model, "predict_proba"):
            probabilities = model.predict_proba(matrix)[0]
        else:
            scores = model.decision_function(matrix)[0]
            scores = scores - np.max(scores)
            probabilities = np.exp(scores) / np.exp(scores).sum()
        all_diseases = {item.nome: item for item in Doenca.objects.prefetch_related("sintomas").all()}
        for index, class_name in enumerate(model.classes_):
            disease = all_diseases.get(str(class_name))
            if disease:
                probabilities[index] *= math.exp(2 * negative_evidence_adjustment(disease, caso))
        if probabilities.sum():
            probabilities = probabilities / probabilities.sum()
        ranked_indices = np.argsort(probabilities)[::-1][:limite]
        names = [str(model.classes_[index]) for index in ranked_indices]
        diseases = {name: all_diseases[name] for name in names if name in all_diseases}
        hypotheses = []
        for index, name in zip(ranked_indices, names):
            disease = diseases.get(name)
            if not disease:
                continue
            hypotheses.append({
                "id": disease.id, "nome": disease.nome, "tipo": disease.tipo,
                "fase_comum": disease.fase_comum, "score": round(float(probabilities[index]), 6),
                "evidencias": [item.nome for item in caso["sintomas"]],
            })
        return self._result(caso, hypotheses, artifact["metadata"]["modelo_selecionado"],
                            artifact["metadata"].get("resultado_teste"))

    def _infer_analytical(self, caso, limite):
        universo = list(Sintoma.objects.order_by("id"))
        observados = caso["sintomas"]
        ids_observados = {item.id for item in observados}
        doencas = list(Doenca.objects.prefetch_related("sintomas"))
        total_combinacoes = sum((2 ** item.sintomas.count()) - 1 for item in doencas)
        candidatos = []

        for doenca in doencas:
            sintomas_doenca = {item.id: item.nome for item in doenca.sintomas.all()}
            n = len(sintomas_doenca)
            combinacoes = max((2 ** n) - 1, 1)
            log_probabilidade = math.log(combinacoes / max(total_combinacoes, 1))
            for sintoma in universo:
                if sintoma.id in sintomas_doenca:
                    presentes = 2 ** max(n - 1, 0)
                else:
                    presentes = 0
                probabilidade = (presentes + 1) / (combinacoes + 2)
                log_probabilidade += math.log(
                    probabilidade if sintoma.id in ids_observados else 1 - probabilidade
                )
            log_probabilidade += context_adjustment(doenca, caso)
            candidatos.append((doenca, log_probabilidade, [
                nome for sintoma_id, nome in sintomas_doenca.items() if sintoma_id in ids_observados
            ]))

        candidatos.sort(key=lambda item: -item[1])
        selecionados = candidatos[:limite] if observados else []
        if selecionados:
            max_log = selecionados[0][1]
            pesos = [math.exp(item[1] - max_log) for item in selecionados]
            normalizador = sum(pesos)
        else:
            pesos, normalizador = [], 1
        hipoteses = [
            {
                "id": doenca.id,
                "nome": doenca.nome,
                "tipo": doenca.tipo,
                "fase_comum": doenca.fase_comum,
                "score": round(peso / normalizador, 6),
                "evidencias": evidencias,
            }
            for (doenca, _, evidencias), peso in zip(selecionados, pesos)
        ]
        return self._result(caso, hipoteses, "Bernoulli Naive Bayes (fallback analítico)")

    def _result(self, caso, hipoteses, model_name, test_metrics=None):
        ids = [item["id"] for item in hipoteses]
        farmacos = Farmaco.objects.filter(doencas_relacionadas__id__in=ids).distinct()[:3]
        return {
            "mecanismo": self.nome,
            "modelo": model_name,
            "modelo_treinado": test_metrics is not None,
            "metricas_teste": test_metrics,
            "sintomas_reconhecidos": [item.nome for item in caso["sintomas"]],
            "sintomas_negados": caso["sintomas_negados"],
            "sintomas_incertos": caso["sintomas_incertos"],
            "variaveis_reconhecidas": caso["variaveis"],
            "alertas": caso["alertas"],
            "hipoteses": hipoteses,
            "farmacos_relacionados": [
                {
                    "nome_comercial": item.nome_comercial,
                    "principio_ativo": item.principio_ativo,
                    "via_administracao": item.via_administracao,
                    "carencia": item.carencia,
                }
                for item in farmacos
            ],
        }


class MotorMachineLearningK10(MotorMachineLearning):
    """Variante treinada com 10 observações por combinação clínica."""

    nome = "machine_learning_k10"
    artifact_path = Path(settings.BASE_DIR) / "machine" / "artifacts_k10" / "model.joblib"
    _artifact = None
    _artifact_mtime = None


class MotorMachineLearningK100(MotorMachineLearning):
    """Variante histórica de alta amostragem (96, apresentada como k≈100)."""

    nome = "machine_learning_k100"
    artifact_path = Path(settings.BASE_DIR) / "machine" / "artifacts" / "model.joblib"
    _artifact = None
    _artifact_mtime = None
