"""Estados de observação distintos, simulados sem alterar as partições-base."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from bulario.utils import is_clinical_symptom

SYMPTOM_STATES = ['presente', 'ausente', 'incerto', 'desconhecido']
INPUT_SCHEMA = 'estados_sintomas_v1'


def validate_split_groups(data_dir):
    groups = {}
    for split in ['treino', 'validacao', 'teste']:
        frame = pd.read_csv(Path(data_dir) / f'{split}.csv', encoding='utf-8-sig', usecols=['combinacao_id'])
        if frame['combinacao_id'].isna().any():
            raise ValueError('Todas as observações devem identificar a combinação-base.')
        groups[split] = set(frame['combinacao_id'])
    if any(groups[a] & groups[b] for a, b in [('treino', 'validacao'), ('treino', 'teste'), ('validacao', 'teste')]):
        raise ValueError('Combinações-base compartilhadas entre partições: treinamento recusado.')


def generate_observation_dataset(data_dir, output_dir, seed=42, positive_rate=0.65,
                                 uncertain_rate=0.15, negative_rate=0.05, clinical_unknown_rate=0.5):
    if not (0 <= positive_rate <= 1 and 0 <= uncertain_rate <= 1 and positive_rate + uncertain_rate <= 1
            and 0 <= negative_rate <= 1 and 0 <= clinical_unknown_rate <= 1):
        raise ValueError('Taxas de observação devem estar em [0,1]; presença + incerteza não pode exceder 1.')
    data_dir, output_dir = Path(data_dir), Path(output_dir)
    if data_dir.resolve() == output_dir.resolve():
        raise ValueError('O conjunto original deve ser preservado em outro diretório.')
    validate_split_groups(data_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    counts, states_count, source_hashes = {}, {state: 0 for state in SYMPTOM_STATES}, {}
    discarded_rows, excluded_columns = {}, set()
    for split in ['treino', 'validacao', 'teste']:
        source = data_dir / f'{split}.csv'
        frame = pd.read_csv(source, encoding='utf-8-sig', low_memory=False)
        all_columns = [column for column in frame if column.startswith('sintoma_')]
        columns = [column for column in all_columns if is_clinical_symptom(column.split('_', 2)[2])]
        excluded_columns.update(set(all_columns) - set(columns))
        if not columns or 'doenca_alvo' not in frame or 'combinacao_id' not in frame:
            raise ValueError('São necessários sintomas binários, doenca_alvo e combinacao_id.')
        truth = frame[columns].to_numpy()
        if not np.isin(truth, [0, 1]).all():
            raise ValueError('O conjunto-base deve conter somente sintomas 0/1.')
        documented = (truth == 1).any(axis=1)
        discarded_rows[split] = int((~documented).sum())
        frame = frame.loc[documented].copy()
        truth = truth[documented]
        if frame.empty:
            raise ValueError('A partição não contém observações com sinais documentados.')
        draws = rng.random(truth.shape)
        states = np.full(truth.shape, 'desconhecido', dtype=object)
        states[(truth == 1) & (draws < positive_rate)] = 'presente'
        states[(truth == 1) & (draws >= positive_rate) & (draws < positive_rate + uncertain_rate)] = 'incerto'
        states[(truth == 0) & (draws < negative_rate)] = 'ausente'
        # O protocolo de triagem exige ao menos um sinal confirmado. Não
        # cria presença de um sinal que não pertence ao perfil sintético.
        for index in np.flatnonzero(~(states == 'presente').any(axis=1)):
            positive_indices = np.flatnonzero(truth[index] == 1)
            if positive_indices.size:
                states[index, rng.choice(positive_indices)] = 'presente'
        state_columns = ['estado_' + column for column in columns]
        frame[state_columns] = pd.DataFrame(states, index=frame.index, columns=state_columns)
        # O contexto omitido também precisa existir no treino; não é uma
        # categoria clínica observada nem um vetor de zeros não treinado.
        from .training import CORE_CLINICAL_COLUMNS
        for column in CORE_CLINICAL_COLUMNS:
            if column in frame:
                frame.loc[rng.random(len(frame)) < clinical_unknown_rate, column] = 'Não informado'
        frame.to_csv(output_dir / f'{split}.csv', index=False, encoding='utf-8-sig')
        counts[split] = len(frame)
        source_hashes[split] = hashlib.sha256(source.read_bytes()).hexdigest()
        for state in states_count:
            states_count[state] += int((states == state).sum())
    metadata = {
        'schema_entrada': INPUT_SCHEMA, 'origem': 'simulacao_sobre_combinacoes_sinteticas',
        'conjunto_base': str(data_dir), 'sha256_fontes': source_hashes, 'semente': seed,
        'registros': counts, 'contagem_estados': states_count,
        'linhas_sem_sinais_documentados_excluidas': discarded_rows,
        'colunas_marcadoras_excluidas': sorted(excluded_columns),
        'taxas_simuladas': {'presente': positive_rate, 'incerto': uncertain_rate, 'ausente': negative_rate},
        'taxa_contexto_nao_informado': clinical_unknown_rate,
        'restricao': 'Ao menos um sinal do perfil é confirmado por registro.',
        'observacao': 'Estados simulados não são observações clínicas; zeros do perfil-base não demonstram ausência real.',
    }
    source_metadata = data_dir / 'metadados.json'
    if source_metadata.exists():
        metadata['versao_base'] = json.loads(source_metadata.read_text(encoding='utf-8')).get('versao_base')
    (output_dir / 'metadados.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    return metadata
