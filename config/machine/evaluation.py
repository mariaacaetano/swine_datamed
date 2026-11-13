"""Avaliação única dos motores reais, com conversão e listas de tamanho variável."""
import time
import re

from bulario.utils import normalize
from bulario.models import Sintoma

PROTOCOL_VERSION = "inferencia_corrigida_v3"


def symptom_name_map():
    return {re.sub(r'[^a-z0-9]+', '_', normalize(s.nome)).strip('_'): s.nome
            for s in Sintoma.objects.all()}


def row_observations(row, columns, names_by_slug=None):
    names_by_slug = names_by_slug or {}

    def original_name(slug):
        return names_by_slug.get(slug, slug.replace('_', ' '))

    state_columns = [column for column in columns if column.startswith("estado_sintoma_")]
    if state_columns:
        names = {column: original_name(column.split("_", 3)[3]) for column in state_columns}
        symptoms = [names[column] for column in state_columns if row[column] == "presente"]
        phrases = [names[column] if row[column] == "presente" else
                   f"não apresenta {names[column]}" if row[column] == "ausente" else
                   f"talvez {names[column]}" for column in state_columns if row[column] != "desconhecido"]
        return symptoms, "; ".join(phrases)
    symptoms = [original_name(column.split("_", 2)[2]) for column in columns
                if column.startswith("sintoma_") and row[column] == 1]
    return symptoms, "; ".join(symptoms)


def evaluate_frame(frame, engines):
    metrics = {}
    names_by_slug = symptom_name_map()
    inputs = [(row_observations(row, frame.columns, names_by_slug), str(row["doenca_alvo"]))
              for _, row in frame.iterrows()]
    for engine in engines:
        cache = {}
        hits_1 = hits_5 = tp = fp = fn = recognized = expected = 0
        elapsed = 0.0
        model_name = None
        for (symptoms, text), target in inputs:
            key = text
            if key not in cache:
                started = time.perf_counter()
                cache[key] = engine.inferir(text, limite=5, incluir_indicacoes=False)
                elapsed += time.perf_counter() - started
            result = cache[key]
            names = [item["nome"] for item in result["hipoteses"]][:5]
            hit = int(target in names)
            hits_1 += int(bool(names) and names[0] == target)
            hits_5 += hit
            tp += hit
            fp += len(names) - hit
            fn += 1 - hit
            observed = {normalize(name) for name in result["sintomas_reconhecidos"]}
            expected += len(symptoms)
            recognized += sum(normalize(name) in observed for name in symptoms)
            model_name = result.get("modelo", model_name)
        total = len(frame)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        metrics[engine.nome] = {
            "registros_teste": total, "entradas_distintas": len(cache),
            "modelo": model_name, "acertos_top_1": hits_1, "acertos_top_5": hits_5,
            "verdadeiros_positivos": tp, "falsos_positivos": fp, "falsos_negativos": fn,
            "acuracia_top_1": hits_1 / total if total else 0.0,
            "acuracia_top_5": hits_5 / total if total else 0.0,
            "precisao_top_5": precision, "recall_top_5": recall,
            "f1_top_5": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
            "cobertura_conversao": recognized / expected if expected else 0.0,
            "tempo_total_entradas_distintas_s": elapsed,
            "tempo_medio_entrada_distinta_s": elapsed / len(cache) if cache else 0.0,
        }
    return metrics
