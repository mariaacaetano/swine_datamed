import json

import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand

from bulario.knowledge_engines import MotorBayesiano, MotorFuzzy, MotorFuzzySanchez
from machine.evaluation import PROTOCOL_VERSION, evaluate_frame


class Command(BaseCommand):
    help = "Avalia Naive Bayes parametrizado, Sugeno e Sanchez nos datasets k10 e k100."

    def handle(self, *args, **options):
        root = settings.BASE_DIR.parent
        for label, data_dir, artifact_dir in [
            ("k10", "machine_learning_k10", "artifacts_k10"),
            ("k100", "machine_learning", "artifacts"),
        ]:
            test_path = root / "generated_data" / data_dir / "teste.csv"
            frame = pd.read_csv(test_path, encoding="utf-8-sig", low_memory=False)
            metrics = evaluate_frame(frame, [MotorBayesiano(), MotorFuzzy(), MotorFuzzySanchez()])
            output = root / "config" / "machine" / artifact_dir / "knowledge_metrics_v3.json"
            output.write_text(json.dumps({
                "protocolo": PROTOCOL_VERSION,
                "conjunto": label,
                "arquivo_teste": str(test_path.relative_to(root)),
                "registros_teste": len(frame),
                "modelos": metrics,
            }, ensure_ascii=False, indent=2), encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"{label}: {output}"))
