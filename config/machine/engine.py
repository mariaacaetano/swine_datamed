import math
import re
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.naive_bayes import BernoulliNB
from django.conf import settings
from bulario.clinical_input import extract_clinical_case
from bulario.models import Doenca, Sintoma
from bulario.contracts import inference_result
from bulario.utils import normalize, clinical_symptoms, is_clinical_symptom


class MotorMachineLearning:
    """Usa o artefato selecionado em validação; mantém fallback analítico explícito."""

    nome = "machine_learning"
    artifact_path = Path(settings.BASE_DIR) / "machine" / "artifacts" / "model.joblib"
    _artifact = None
    _artifact_mtime = None

    def inferir(self, texto, limite=5, incluir_indicacoes=True):
        return self.inferir_caso(extract_clinical_case(texto), limite, incluir_indicacoes)

    def inferir_caso(self, caso, limite=5, incluir_indicacoes=True):
        artifact = self._load_artifact()
        if artifact is not None:
            return self._infer_trained(caso, artifact, limite, incluir_indicacoes)
        return self._infer_analytical(caso, limite, incluir_indicacoes)

    @classmethod
    def _load_artifact(cls):
        if not cls.artifact_path.exists():
            return None
        mtime = cls.artifact_path.stat().st_mtime_ns
        if cls._artifact is None or cls._artifact_mtime != mtime:
            cls._artifact = joblib.load(cls.artifact_path)
            required = {"metadata", "model", "preprocessor", "feature_columns", "symptom_columns", "categorical_columns"}
            if not isinstance(cls._artifact, dict) or not required.issubset(cls._artifact):
                cls._artifact = None
                raise ValueError("Artefato incompatível com o contrato de inferência.")
            cls._artifact_mtime = mtime
        return cls._artifact

    def _infer_trained(self, caso, artifact, limite, incluir_indicacoes=True):
        model_name = artifact["metadata"]["modelo_selecionado"]
        state_columns = artifact.get("symptom_state_columns", [])
        state_policy = "Presença, ausência, incerteza e desconhecimento codificados em categorias distintas."
        if not caso["sintomas"]:
            result = self._result(caso, [], model_name, artifact["metadata"].get("resultado_teste"), incluir_indicacoes)
            if state_columns:
                result.update({"politica_ausencia": state_policy, "schema_entrada": "estados_sintomas_v1"})
            return result
        row = {name: "desconhecido" if name.startswith("estado_sintoma_") else
                     0 if name.startswith("sintoma_") else "Não informado"
               for name in artifact["feature_columns"]}
        known_columns = set()
        columns_by_name = {re.sub(r"^sintoma_\d+_", "", column): column for column in artifact["symptom_columns"]}
        for symptom in caso["sintomas"]:
            suffix = re.sub(r"[^a-z0-9]+", "_", normalize(symptom.nome)).strip("_")
            column = columns_by_name.get(suffix)
            if column:
                row[column] = 1
                known_columns.add(column)
        for name in caso["sintomas_negados"]:
            suffix = re.sub(r"[^a-z0-9]+", "_", normalize(name)).strip("_")
            column = columns_by_name.get(suffix)
            if column:
                known_columns.add(column)
        if state_columns:
            state_by_name = {re.sub(r"^estado_sintoma_\d+_", "", column): column for column in state_columns}
            observations = [([s.nome for s in caso["sintomas"]], "presente"),
                            (caso["sintomas_negados"], "ausente"), (caso["sintomas_incertos"], "incerto")]
            for names, state in observations:
                for name in names:
                    suffix = re.sub(r"[^a-z0-9]+", "_", normalize(name)).strip("_")
                    column = state_by_name.get(suffix)
                    if column:
                        row[column] = state
        variables = caso["variaveis"]
        temperature = variables["classificacao_temperatura"]
        temperature_values = {
            "hipotermia": "<37,0 (hipotermia)", "normal": "37,0–39,5 (normal)",
            "febre": "39,6–40,0 (febre)", "febre alta": ">40,0 (febre alta)",
        }
        values = {
            "Temperatura corporal (°C)": temperature_values.get(temperature, "Não informado"),
            "Idade": variables["idade_categoria"] or "Não informado",
            "Gênero": variables["genero"] or "Não informado",
            "Fase reprodutiva": variables["fase_reprodutiva"] or "Não informado",
            "Estado reprodutivo": variables["estado_reprodutivo"] or "Não informado",
            "Duração dos sintomas": variables["duracao_categoria"] or "Não informado",
        }
        row.update({name: value for name, value in values.items() if name in row})
        frame = pd.DataFrame([row], columns=artifact["feature_columns"])
        matrix = artifact["preprocessor"].transform(frame)
        model = artifact["model"]
        if isinstance(model, BernoulliNB):
            # Marginaliza os Bernoullis desconhecidos. Não informar um sinal
            # deixa de equivaler a observar sua ausência.
            mask = [column in known_columns for column in artifact["symptom_columns"]]
            if state_columns:
                states_encoder = artifact["preprocessor"].named_transformers_["states"]
                for column, categories in zip(state_columns, states_encoder.categories_):
                    mask.extend([row[column] != "desconhecido"] * len(categories))
            encoder = artifact["preprocessor"].named_transformers_["clinical"]
            for column, categories in zip(artifact["categorical_columns"], encoder.categories_):
                known = row[column] != "Não informado" and row[column] in categories
                mask.extend([known] * len(categories))
            probabilities = self._predict_partial_bernoulli(model, matrix, np.asarray(mask))
            absence_policy = "Variáveis desconhecidas/incertas marginalizadas; negações usam a probabilidade complementar."
        elif hasattr(model, "predict_proba"):
            probabilities = model.predict_proba(matrix)[0]
            absence_policy = state_policy if state_columns else "Artefato binário: sintomas desconhecidos/incertos codificados como zero, conforme o treino."
        else:
            scores = model.decision_function(matrix)[0]
            scores = scores - np.max(scores)
            probabilities = np.exp(scores) / np.exp(scores).sum()
            absence_policy = "Artefato binário: sintomas desconhecidos/incertos codificados como zero, conforme o treino."
        all_diseases = {item.nome: item for item in Doenca.objects.prefetch_related("sintomas").all()
                       if clinical_symptoms(item)}
        # Restringe o universo às classes com perfil documentado. Isso também
        # permite usar o Bernoulli histórico sem atribuir massa a classes
        # cujo único "sintoma" era um marcador de informação faltante.
        supported = np.asarray([str(name) in all_diseases for name in model.classes_])
        total_supported = probabilities[supported].sum()
        if total_supported > 0:
            probabilities = np.where(supported, probabilities / total_supported, 0.0)
        else:
            return self._result(caso, [], model_name, artifact["metadata"].get("resultado_teste"), incluir_indicacoes)
        ranked_indices = sorted((i for i, name in enumerate(model.classes_) if str(name) in all_diseases),
                                key=lambda i: (-probabilities[i], str(model.classes_[i])))[:max(0, limite)]
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
                "evidencias": [item.nome for item in caso["sintomas"] if item in disease.sintomas.all()],
            })
        result = self._result(caso, hypotheses, model_name,
                              artifact["metadata"].get("resultado_teste"), incluir_indicacoes)
        result["politica_ausencia"] = absence_policy
        result["schema_entrada"] = "estados_sintomas_v1" if state_columns else "sintomas_binarios"
        result["universo_classes"] = "Enfermidades cadastradas com perfil sintomático documentado; probabilidades condicionadas a esse universo."
        result["protocolo_metricas_teste"] = ("Estados simulados e variáveis clínicas do CSV; não representam validação clínica externa."
                                               if state_columns else "Métricas históricas do vetor completo de treino; não avaliam a entrada parcial atual.")
        return result

    @staticmethod
    def _predict_partial_bernoulli(model, matrix, mask):
        values = matrix.toarray()[0] if hasattr(matrix, "toarray") else np.asarray(matrix)[0]
        log_present = model.feature_log_prob_[:, mask]
        log_absent = np.log1p(-np.exp(log_present))
        observed = values[mask]
        scores = model.class_log_prior_ + (log_present * observed + log_absent * (1 - observed)).sum(axis=1)
        weights = np.exp(scores - scores.max())
        return weights / weights.sum()

    def _infer_analytical(self, caso, limite, incluir_indicacoes=True):
        universo = [s for s in Sintoma.objects.order_by("id") if is_clinical_symptom(s.nome)]
        observados = caso["sintomas"]
        ids_observados = {item.id for item in observados}
        negados = {normalize(name) for name in caso["sintomas_negados"]}
        doencas = [item for item in Doenca.objects.prefetch_related("sintomas") if clinical_symptoms(item)]
        total_combinacoes = sum((2 ** len(clinical_symptoms(item))) - 1 for item in doencas)
        candidatos = []

        for doenca in doencas:
            sintomas_doenca = {item.id: item.nome for item in clinical_symptoms(doenca)}
            n = len(sintomas_doenca)
            combinacoes = max((2 ** n) - 1, 1)
            log_probabilidade = math.log(combinacoes / max(total_combinacoes, 1))
            for sintoma in universo:
                if sintoma.id not in ids_observados and normalize(sintoma.nome) not in negados:
                    continue
                if sintoma.id in sintomas_doenca:
                    presentes = 2 ** max(n - 1, 0)
                else:
                    presentes = 0
                probabilidade = (presentes + 1) / (combinacoes + 2)
                log_probabilidade += math.log(
                    probabilidade if sintoma.id in ids_observados else 1 - probabilidade
                )
            candidatos.append((doenca, log_probabilidade, [
                nome for sintoma_id, nome in sintomas_doenca.items() if sintoma_id in ids_observados
            ]))

        candidatos.sort(key=lambda item: -item[1])
        selecionados = candidatos if observados else []
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
            for (doenca, _, evidencias), peso in list(zip(selecionados, pesos))[:max(0, limite)]
        ]
        return self._result(caso, hipoteses, "Bernoulli Naive Bayes (fallback analítico)",
                            incluir_indicacoes=incluir_indicacoes)

    def _result(self, caso, hipoteses, model_name, test_metrics=None, incluir_indicacoes=True):
        return inference_result(caso, hipoteses, self.nome, incluir_indicacoes,
            modelo=model_name, modelo_treinado=test_metrics is not None,
            tipo_score="probabilidade_modelo", calibracao_clinica=False,
            politica_ausencia=("Variáveis desconhecidas/incertas marginalizadas."
                              if "Bernoulli" in model_name else
                              "Artefato binário: desconhecidos/incertos codificados como zero, conforme o treino."),
            metricas_teste=test_metrics)


class MotorMachineLearningK10(MotorMachineLearning):
    """Random Forest com quatro estados, derivado das partições k=10."""

    nome = "machine_learning_k10"
    artifact_path = Path(settings.BASE_DIR) / "machine" / "artifacts_states" / "model.joblib"
    _artifact = None
    _artifact_mtime = None


class MotorMachineLearningK100(MotorMachineLearning):
    """Variante histórica de alta amostragem (100 variações por combinação)."""

    nome = "machine_learning_k100"
    artifact_path = Path(settings.BASE_DIR) / "machine" / "artifacts" / "model.joblib"
    _artifact = None
    _artifact_mtime = None
