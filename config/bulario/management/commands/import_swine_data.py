from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from bulario.data_pipeline import generate_clinical_dataset, generate_dataset, generate_ml_dataset, import_base_data


class Command(BaseCommand):
    help = "Importa os CSVs e gera as combinações exaustivas de sintomas por doença."

    def add_arguments(self, parser):
        parser.add_argument("--clear", action="store_true", help="Substitui a base relacional atual.")
        parser.add_argument("--generate", action="store_true", help="Gera também o dataset sintético.")
        parser.add_argument("--total", type=int, default=None, help="Limite opcional; por padrão gera todas as combinações.")
        parser.add_argument("--seed", type=int, default=42)
        parser.add_argument("--output", default="generated_data/dataset_combinacoes_sintomas.csv")
        parser.add_argument("--clinical-output", default="generated_data/dataset_clinico_ampliado.csv")
        parser.add_argument("--variations", type=int, default=10, help="Observações clínicas por combinação de sintomas.")
        parser.add_argument("--ml-variations", type=int, default=96, help="Observações por combinação para machine learning.")
        parser.add_argument("--ml-output", default="generated_data/machine_learning")

    def handle(self, *args, **options):
        try:
            summary = import_base_data(settings.BASE_DIR.parent / "base_data", clear=options["clear"])
            self.stdout.write(self.style.SUCCESS("Importação concluída: " + ", ".join(f"{v} {k}" for k, v in summary.items())))
            if options["generate"]:
                output = settings.BASE_DIR.parent / options["output"]
                generation = generate_dataset(output, total=options["total"], seed=options["seed"])
                self.stdout.write(self.style.SUCCESS(
                    f"Dataset criado: {generation.total_registros} combinações em {generation.arquivo}."
                ))
                clinical = generate_clinical_dataset(
                    settings.BASE_DIR.parent / options["clinical_output"],
                    variations_per_combination=options["variations"], seed=options["seed"], replace=False,
                )
                self.stdout.write(self.style.SUCCESS(
                    f"Dataset clínico criado: {clinical.total_registros} observações em {clinical.arquivo}."
                ))
                ml_summary = generate_ml_dataset(
                    settings.BASE_DIR.parent / options["ml_output"],
                    variations_per_combination=options["ml_variations"], seed=options["seed"],
                )
                self.stdout.write(self.style.SUCCESS(
                    f"Dataset de ML criado: {ml_summary['total']} registros em {options['ml_output']}."
                ))
        except (OSError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
