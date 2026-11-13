import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from machine.observations import generate_observation_dataset


class Command(BaseCommand):
    help = 'Gera estados presente, ausente, incerto e desconhecido em partições sintéticas existentes.'

    def add_arguments(self, parser):
        parser.add_argument('--data-dir', default='generated_data/machine_learning_k10')
        parser.add_argument('--output', default='generated_data/machine_learning_states')
        parser.add_argument('--seed', type=int, default=42)
        parser.add_argument('--positive-rate', type=float, default=0.65)
        parser.add_argument('--uncertain-rate', type=float, default=0.15)
        parser.add_argument('--negative-rate', type=float, default=0.05)
        parser.add_argument('--clinical-unknown-rate', type=float, default=0.5)

    def handle(self, *args, **options):
        root = settings.BASE_DIR.parent
        try:
            result = generate_observation_dataset(root / options['data_dir'], root / options['output'],
                        options['seed'], options['positive_rate'], options['uncertain_rate'], options['negative_rate'],
                        options['clinical_unknown_rate'])
        except (OSError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
