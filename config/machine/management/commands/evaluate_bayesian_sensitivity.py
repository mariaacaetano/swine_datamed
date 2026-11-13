"""Estabilidade dos parâmetros manuais; não estima CPTs clínicas."""
import hashlib
import json
from datetime import datetime, timezone

import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from bulario.knowledge_engines import MotorBayesiano
from machine.evaluation import row_observations, symptom_name_map


class Command(BaseCommand):
    help = 'Compara rankings bayesianos em cenários manuais; não calibra probabilidades clínicas.'

    def add_arguments(self, parser):
        parser.add_argument('--data', default='generated_data/machine_learning_states/teste.csv')
        parser.add_argument('--output', default='config/machine/artifacts_states/bayesian_sensitivity.json')
        parser.add_argument('--limit', type=int, default=300)
        parser.add_argument('--seed', type=int, default=42)

    def handle(self, *args, **options):
        root = settings.BASE_DIR.parent
        source = root / options['data']
        frame = pd.read_csv(source, encoding='utf-8-sig', low_memory=False)
        if frame.empty or not any(column.startswith('sintoma_') for column in frame) or options['limit'] <= 0:
            raise CommandError('São necessários registros com sintomas e um limite positivo.')
        names_by_slug = symptom_name_map()
        texts = list(dict.fromkeys(row_observations(row, frame.columns, names_by_slug)[1] for _, row in frame.iterrows()))
        texts = pd.Series(texts).sample(n=min(len(texts), options['limit']), random_state=options['seed']).tolist()

        def ranking(engine, text):
            return [h['nome'] for h in engine.inferir(text, limite=5, incluir_indicacoes=False)['hipoteses']]

        reference = [ranking(MotorBayesiano(), text) for text in texts]
        scenarios = []
        for associated in [0.6, 0.8, 0.95]:
            for unrelated in [0.05, 0.2, 0.4]:
                engine = MotorBayesiano(associated, unrelated)
                ranks = reference if (associated, unrelated) == (0.8, 0.2) else [ranking(engine, text) for text in texts]
                matches = sum(a[:1] == b[:1] for a, b in zip(reference, ranks))
                overlap = sum(len(set(a) & set(b)) / len(set(a) | set(b)) if a or b else 1.0
                              for a, b in zip(reference, ranks))
                scenarios.append({'p_associado': associated, 'p_nao_associado': unrelated,
                                  'concordancia_top_1_com_referencia': matches / len(texts),
                                  'jaccard_medio_top_5_com_referencia': overlap / len(texts)})
        report = {'criado_em': datetime.now(timezone.utc).isoformat(), 'arquivo': options['data'],
                  'sha256_fonte': hashlib.sha256(source.read_bytes()).hexdigest(),
                  'semente': options['seed'], 'entradas_distintas_avaliadas': len(texts),
                  'referencia': {'p_associado': 0.8, 'p_nao_associado': 0.2}, 'cenarios': scenarios,
                  'interpretacao': 'Estabilidade de ranking em observações sintéticas, sem ajuste pelo alvo.',
                  'limite': 'A base de associações não identifica prevalências nem CPTs clínicas. '
                            'Concordância alta não valida valores absolutos do posterior. '
                            'Em casos só positivos, pares com p_associado > p_nao_associado '
                            'preservam a ordenação por quantidade de associações.'}
        output = root / options['output']
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(f'Análise de sensibilidade gravada em {output}'))
