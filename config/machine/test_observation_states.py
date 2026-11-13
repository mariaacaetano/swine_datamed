from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import joblib
import pandas as pd
from django.test import SimpleTestCase, TestCase

from bulario.models import Doenca, Sintoma
from machine.engine import MotorMachineLearningK10
from machine.evaluation import row_observations
from machine.observations import SYMPTOM_STATES, generate_observation_dataset
from machine.training import train_and_evaluate


def write_source(directory):
    directory.mkdir()
    for part, offset in [('treino', 0), ('validacao', 100), ('teste', 200)]:
        pd.DataFrame([{'combinacao_id': offset + index, 'observacao_id': offset + index,
                       'sintoma_001_tosse': 1, 'sintoma_002_febre': index % 2,
                       'sintoma_003_dispneia': 1 - index % 2, 'sintoma_004_apatia': 0,
                       'Idade': '22–70 dias', 'doenca_alvo': 'A' if index % 2 else 'B'}
                      for index in range(30)]).to_csv(directory / f'{part}.csv', index=False)


class ObservationDatasetTests(SimpleTestCase):
    def test_simulation_preserves_splits_and_truth_and_is_reproducible(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            write_source(source)
            metadata = generate_observation_dataset(source, root / 'first')
            generate_observation_dataset(source, root / 'second')
            states = set()
            for part in ['treino', 'validacao', 'teste']:
                original = pd.read_csv(source / f'{part}.csv')
                generated = pd.read_csv(root / 'first' / f'{part}.csv')
                pd.testing.assert_series_equal(original.combinacao_id, generated.combinacao_id)
                pd.testing.assert_series_equal(original.doenca_alvo, generated.doenca_alvo)
                self.assertEqual((root / 'first' / f'{part}.csv').read_bytes(),
                                 (root / 'second' / f'{part}.csv').read_bytes())
                cols = [column for column in generated if column.startswith('estado_sintoma_')]
                self.assertTrue((generated[cols] == 'presente').any(axis=1).all())
                for column in cols:
                    truth = generated[column.removeprefix('estado_')]
                    self.assertFalse(((generated[column] == 'presente') & (truth == 0)).any())
                    self.assertFalse(((generated[column] == 'ausente') & (truth == 1)).any())
                    states.update(generated[column])
            self.assertEqual(states, set(SYMPTOM_STATES))
            self.assertEqual(metadata['origem'], 'simulacao_sobre_combinacoes_sinteticas')

    def test_overlap_between_base_groups_is_rejected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            write_source(source)
            (source / 'teste.csv').write_bytes((source / 'treino.csv').read_bytes())
            with self.assertRaises(ValueError):
                generate_observation_dataset(source, root / 'observed')

    def test_evaluator_never_reads_hidden_truth_when_states_exist(self):
        row = pd.Series({'sintoma_001_tosse': 1, 'sintoma_002_febre': 1,
                         'estado_sintoma_001_tosse': 'presente', 'estado_sintoma_002_febre': 'desconhecido'})
        symptoms, text = row_observations(row, row.index)
        self.assertEqual(symptoms, ['tosse'])
        self.assertEqual(text, 'tosse')
        row['estado_sintoma_002_febre'] = 'ausente'
        self.assertEqual(row_observations(row, row.index)[1], 'tosse; não apresenta febre')

    def test_missing_information_marker_is_excluded_from_features_and_empty_profiles(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            write_source(source)
            for part in ['treino', 'validacao', 'teste']:
                path = source / f'{part}.csv'
                frame = pd.read_csv(path)
                columns = [c for c in frame if c.startswith('sintoma_')]
                frame['sintoma_005_nao_informado_no_documento'] = 0
                frame.loc[0, columns] = 0
                frame.loc[0, 'sintoma_005_nao_informado_no_documento'] = 1
                frame.to_csv(path, index=False)
            metadata = generate_observation_dataset(source, root / 'observed')
            self.assertEqual(metadata['linhas_sem_sinais_documentados_excluidas'],
                             {'treino': 1, 'validacao': 1, 'teste': 1})
            for part in ['treino', 'validacao', 'teste']:
                frame = pd.read_csv(root / 'observed' / f'{part}.csv')
                self.assertEqual(len(frame), 29)
                self.assertNotIn('estado_sintoma_005_nao_informado_no_documento', frame.columns)


class RandomForestStateInputTests(TestCase):
    def test_training_and_runtime_use_same_four_states_without_truth_leakage(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            write_source(source)
            generate_observation_dataset(source, root / 'observed')
            metadata = train_and_evaluate(root / 'observed', root / 'artifact', model_name='Random Forest')
            artifact = joblib.load(root / 'artifact' / 'model.joblib')
            self.assertEqual(metadata['schema_entrada'], 'estados_sintomas_v1')
            self.assertEqual(artifact['symptom_columns'], [])
            self.assertFalse(any(column.startswith('sintoma_') for column in artifact['feature_columns']))
            for name in ['Tosse', 'Febre', 'Dispneia', 'Apatia']:
                Sintoma.objects.create(nome=name)
            for name in ['A', 'B']:
                disease = Doenca.objects.create(nome=name)
                disease.sintomas.add(Sintoma.objects.get(nome='Tosse'))
            processor = artifact['preprocessor']
            vectors = []
            for text, expected in [('tosse; febre', 'presente'), ('tosse; sem febre', 'ausente'),
                                   ('tosse; talvez febre', 'incerto'), ('tosse', 'desconhecido')]:
                with self.subTest(state=expected), patch.object(MotorMachineLearningK10, '_load_artifact', return_value=artifact), \
                        patch.object(processor, 'transform', wraps=processor.transform) as transform:
                    result = MotorMachineLearningK10().inferir(text, incluir_indicacoes=False)
                    frame = transform.call_args.args[0]
                    self.assertEqual(frame['estado_sintoma_002_febre'].iloc[0], expected)
                    matrix = processor.transform(frame)
                    vectors.append(tuple(matrix.toarray()[0] if hasattr(matrix, 'toarray') else matrix[0]))
                    self.assertTrue(result['modelo_treinado'])
                    self.assertEqual(result['modelo'], 'Random Forest')
            self.assertEqual(len(set(vectors)), 4)
