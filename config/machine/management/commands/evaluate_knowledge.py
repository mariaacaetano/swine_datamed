import json
import math
import re
from pathlib import Path

import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand

from bulario.models import Doenca, Sintoma
from bulario.utils import normalize


def evaluate(frame, diseases, symptom_by_column):
    results = {"rede_bayesiana": {"top_1": 0, "top_5": 0}, "fuzzy": {"top_1": 0, "top_5": 0}}
    total = len(frame)
    # Materializa as relações uma única vez. Consultar disease.sintomas dentro
    # do laço de avaliação fazia uma consulta repetida para cada caso/doença.
    disease_symptoms = [
        (disease.nome, {symptom.id for symptom in disease.sintomas.all()})
        for disease in diseases
    ]
    for _, row in frame.iterrows():
        observed = {symptom_by_column[re.sub(r"^sintoma_\d+_", "", column)].id
                    for column in row.index
                    if column.startswith("sintoma_")
                    and re.sub(r"^sintoma_\d+_", "", column) in symptom_by_column
                    and row.get(column, 0) == 1}
        rankings = {"rede_bayesiana": [], "fuzzy": []}
        for disease_name, symptoms in disease_symptoms:
            if not symptoms:
                continue
            present = sum(symptom_id in observed for symptom_id in symptoms)
            bayes = sum(math.log(0.8 if symptom_id in observed else 0.2)
                        for symptom_id in symptoms)
            fuzzy = present / len(symptoms)
            rankings["rede_bayesiana"].append((bayes, disease_name))
            rankings["fuzzy"].append((fuzzy, disease_name))
        target = str(row["doenca_alvo"])
        for name, ranking in rankings.items():
            ordered = [item[1] for item in sorted(ranking, reverse=True)[:5]]
            results[name]["top_1"] += int(bool(ordered and ordered[0] == target))
            results[name]["top_5"] += int(target in ordered)
    for result in results.values():
        result["acuracia_top_1"] = result.pop("top_1") / total if total else 0
        result["acuracia_top_5"] = result.pop("top_5") / total if total else 0
        result["registros_teste"] = total
    return results


class Command(BaseCommand):
    help = "Avalia Rede Bayesiana e Fuzzy nos datasets k10 e k100."

    def handle(self, *args, **options):
        root = settings.BASE_DIR.parent
        diseases = list(Doenca.objects.prefetch_related("sintomas").all())
        symptom_by_column = {re.sub(r"^sintoma_\d+_", "", column): symptom
                             for symptom in Sintoma.objects.all()
                             for column in [f"sintoma_000_{re.sub(r'[^a-z0-9]+', '_', normalize(symptom.nome)).strip('_')}"]}
        symptom_by_column = {re.sub(r"^sintoma_\d+_", "", key): value for key, value in symptom_by_column.items()}
        # The generated files may use a different numeric ordering; match by suffix.
        symptom_by_column = {re.sub(r"^sintoma_\d+_", "", f"sintoma_000_{key}"): value
                             for key, value in symptom_by_column.items()}
        for label, data_dir, artifact_dir in [
            ("k10", "machine_learning_k10", "artifacts_k10"),
            ("k100", "machine_learning", "artifacts"),
        ]:
            test_path = root / "generated_data" / data_dir / "teste.csv"
            frame = pd.read_csv(test_path, low_memory=False)
            metrics = evaluate(frame, diseases, symptom_by_column)
            output = root / "config" / "machine" / artifact_dir / "knowledge_metrics.json"
            output.write_text(json.dumps({
                "conjunto": label,
                "arquivo_teste": str(test_path.relative_to(root)),
                "registros_teste": len(frame),
                "modelos": metrics,
            }, ensure_ascii=False, indent=2), encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"{label}: {output}"))
