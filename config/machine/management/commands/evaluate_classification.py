import json
from datetime import datetime, timezone

import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from bulario.knowledge_engines import MotorBayesiano, MotorFuzzy, MotorFuzzySanchez
from machine.engine import MotorMachineLearning, MotorMachineLearningK10
from machine.evaluation import PROTOCOL_VERSION, evaluate_frame
from regras.chaining import MotorRegrasEncadeadas
from regras.engine import MotorRegras
from semantica.engine import MotorSemantico


class Command(BaseCommand):
    help = "Avalia os oito motores atuais, sem consultar indicações do bulário."
    default_output = "config/machine/artifacts/classification_metrics_v3.json"

    def add_arguments(self, parser):
        parser.add_argument("--data", default="generated_data/machine_learning_k10/teste.csv")
        parser.add_argument("--output", default=self.default_output)
        parser.add_argument("--sample-size", type=int)
        parser.add_argument("--seed", type=int, default=42)

    def handle(self, *args, **options):
        root = settings.BASE_DIR.parent
        frame = pd.read_csv(root / options["data"], encoding="utf-8-sig", low_memory=False)
        if frame.empty:
            raise CommandError("O conjunto de teste está vazio.")
        if "doenca_alvo" not in frame or not any(column.startswith("sintoma_") for column in frame):
            raise CommandError("O CSV deve conter doenca_alvo e colunas sintoma_<id>_<nome>.")
        population = len(frame)
        if options["sample_size"] is not None:
            if options["sample_size"] <= 0:
                raise CommandError("O tamanho da amostra deve ser positivo.")
            frame = frame.sample(n=min(population, options["sample_size"]), random_state=options["seed"])
        engines = [MotorRegras(), MotorRegrasEncadeadas(), MotorSemantico(),
                   MotorMachineLearning(), MotorMachineLearningK10(), MotorBayesiano(), MotorFuzzy(), MotorFuzzySanchez()]
        metrics = evaluate_frame(frame, engines)
        output = root / options["output"]
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({
            "protocolo": PROTOCOL_VERSION,
            "criado_em": datetime.now(timezone.utc).isoformat(),
            "arquivo_teste": options["data"], "fases": ["conversao", "classificacao"],
            "populacao_arquivo": population, "registros_avaliados": len(frame),
            "semente_amostra": options["seed"] if options["sample_size"] else None,
            "entrada": ("Estados relatados dos sintomas; colunas binárias de origem não entram na inferência."
                        if any(column.startswith("estado_sintoma_") for column in frame)
                        else "Somente sintomas positivos; omitidos são desconhecidos."),
            "contexto_clinico": "Não fornecido: todos os motores recebem somente os mesmos sintomas relatados.",
            "origem_dados": "Sintética, derivada das associações cadastradas; não mede desempenho clínico.",
            "tempo": "Conversão e classificação conjuntas; cache por entrada, sem consultas terapêuticas.",
            "modelos": metrics,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Avaliação de classificação gravada em {output}"))
