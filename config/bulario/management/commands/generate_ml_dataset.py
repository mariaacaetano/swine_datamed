import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from bulario.data_pipeline import generate_ml_dataset


class Command(BaseCommand):
    help = "Gera somente o dataset de machine learning, sem alterar as demais versões."

    def add_arguments(self, parser):
        parser.add_argument("--k", type=int, required=True, help="Variações por combinação.")
        parser.add_argument("--output", required=True, help="Diretório de saída relativo à raiz do projeto.")
        parser.add_argument("--seed", type=int, default=42)

    def handle(self, *args, **options):
        try:
            output_dir = settings.BASE_DIR.parent / options["output"]
            summary = generate_ml_dataset(
                output_dir,
                variations_per_combination=options["k"],
                seed=options["seed"],
            )
        except (OSError, ValueError) as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(json.dumps({
            **summary,
            "diretorio": str(output_dir),
        }, ensure_ascii=False, indent=2)))
