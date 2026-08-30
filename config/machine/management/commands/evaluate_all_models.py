import json
import time
from pathlib import Path

import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand

from bulario.knowledge_engines import MotorBayesiano, MotorFuzzy
from regras.engine import MotorRegras
from semantica.engine import MotorSemantico
from machine.engine import MotorMachineLearning


class Command(BaseCommand):
    help = "Compara todos os motores no mesmo conjunto de teste rotulado."

    def add_arguments(self, parser):
        parser.add_argument("--data", default="generated_data/machine_learning_k10/teste.csv")
        parser.add_argument("--output", default="config/machine/artifacts/comparative_metrics.json")

    def handle(self, *args, **options):
        root = settings.BASE_DIR.parent
        frame = pd.read_csv(root / options["data"], encoding="utf-8-sig", low_memory=False)
        engines = [MotorRegras(), MotorSemantico(), MotorMachineLearning(), MotorBayesiano(), MotorFuzzy()]
        stats = {engine.nome: {"top_1": 0, "top_5": 0, "tempo_total_s": 0.0} for engine in engines}
        cache = {engine.nome: {} for engine in engines}
        for _, row in frame.iterrows():
            symptoms = [column.rsplit("_", 1)[-1].replace("_", " ") for column in row.index
                        if column.startswith("sintoma_") and row[column] == 1]
            text_input = "; ".join(symptoms)
            target = str(row["doenca_alvo"])
            for engine in engines:
                key = tuple(sorted(symptoms))
                if key not in cache[engine.nome]:
                    started = time.perf_counter()
                    cache[engine.nome][key] = engine.inferir(text_input, limite=5)
                    stats[engine.nome]["tempo_total_s"] += time.perf_counter() - started
                result = cache[engine.nome][key]
                names = [item["nome"] for item in result.get("hipoteses", [])]
                stats[engine.nome]["top_1"] += int(bool(names and names[0] == target))
                stats[engine.nome]["top_5"] += int(target in names)
        total = len(frame)
        for values in stats.values():
            values["registros_teste"] = total
            values["acuracia_top_1"] = values.pop("top_1") / total
            values["acuracia_top_5"] = values.pop("top_5") / total
            values["tempo_medio_por_caso_s"] = values["tempo_total_s"] / total
            values["precisao_top_5"] = values["acuracia_top_5"] / 5
            values["recall_top_5"] = values["acuracia_top_5"]
            values["f1_top_5"] = 2 * values["precisao_top_5"] * values["recall_top_5"] / (values["precisao_top_5"] + values["recall_top_5"]) if values["acuracia_top_5"] else 0
        output = root / options["output"]
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({"arquivo_teste": options["data"], "modelos": stats}, ensure_ascii=False, indent=2), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Métricas comparativas gravadas em {output}"))
