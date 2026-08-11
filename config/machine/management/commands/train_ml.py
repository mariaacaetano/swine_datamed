import json

from django.conf import settings
from django.core.management.base import BaseCommand

from machine.training import train_and_evaluate


class Command(BaseCommand):
    help = "Treina, seleciona, avalia e serializa o modelo de aprendizado de máquina."

    def add_arguments(self, parser):
        parser.add_argument("--data-dir", default="generated_data/machine_learning")
        parser.add_argument("--artifact-dir", default="config/machine/artifacts")
        parser.add_argument("--seed", type=int, default=42)

    def handle(self, *args, **options):
        root = settings.BASE_DIR.parent
        data_dir = root / options["data_dir"]
        artifact_dir = root / options["artifact_dir"]
        metadata = train_and_evaluate(data_dir, artifact_dir, seed=options["seed"])
        self.stdout.write(self.style.SUCCESS(json.dumps({
            "modelo": metadata["modelo_selecionado"],
            "validacao": metadata["resultados_validacao"][metadata["modelo_selecionado"]],
            "teste": metadata["resultado_teste"],
            "artefato": str(artifact_dir / "model.joblib"),
        }, ensure_ascii=False, indent=2)))
