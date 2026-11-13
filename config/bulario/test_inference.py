"""Regressões semânticas e verificações numéricas dos modelos experimentais."""
from django.test import TestCase

from bulario.clinical_input import extract_clinical_case
from bulario.knowledge_engines import (MotorBayesiano, MotorFuzzy, MotorFuzzySanchez,
                                      composicao_max_min, inferir_sugeno, pertinencias)
from bulario.models import Doenca, Sintoma
from bulario.views import _adicionar_graus_avaliacao


class ClinicalInputRegressionTests(TestCase):
    def setUp(self):
        for name in ['Tosse', 'Febre', 'Febre alta', 'Dispneia', 'Perda de apetite', 'Diarreia']:
            Sintoma.objects.create(nome=name)

    def test_negation_applies_to_aliases(self):
        case = extract_clinical_case('não está tossindo; não está respirando pesado')
        self.assertEqual(case['sintomas'], [])
        self.assertEqual(set(case['sintomas_negados']), {'Tosse', 'Dispneia'})

    def test_intrinsically_negative_aliases_still_mean_positive_sign(self):
        for text in ['sem apetite', 'não quis a ração']:
            with self.subTest(text=text):
                case = extract_clinical_case(text)
                self.assertIn('Perda de apetite', [s.nome for s in case['sintomas']])
                self.assertEqual(case['sintomas_negados'], [])

    def test_last_mention_wins_in_both_directions(self):
        for text, present in [('Tosse. Agora não apresenta tosse.', False),
                              ('Não apresenta tosse. Agora está tossindo.', True)]:
            with self.subTest(text=text):
                case = extract_clinical_case(text)
                self.assertEqual('Tosse' in [s.nome for s in case['sintomas']], present)
                self.assertEqual('Tosse' in case['sintomas_negados'], not present)

    def test_uncertain_is_disjoint_from_confirmed_and_scoped_to_clause(self):
        case = extract_clinical_case('talvez tosse. Febre confirmada')
        self.assertEqual(case['sintomas_incertos'], ['Tosse'])
        self.assertEqual([s.nome for s in case['sintomas']], ['Febre'])
        case = extract_clinical_case('talvez tosse\nfebre confirmada')
        self.assertEqual(case['sintomas_incertos'], ['Tosse'])

    def test_age_does_not_become_temperature_or_symptom_duration(self):
        case = extract_clinical_case('40 dias de idade')
        self.assertEqual(case['sintomas'], [])
        self.assertIsNone(case['variaveis']['temperatura_corporal_c'])
        self.assertIsNone(case['variaveis']['duracao_horas'])
        self.assertEqual(case['variaveis']['idade_categoria'], '22–70 dias')
        self.assertEqual(case['variaveis']['idade_dias'], 40)

    def test_age_and_duration_remain_independent(self):
        case = extract_clinical_case('leitão de 40 dias com tosse há 2 dias')
        self.assertEqual(case['variaveis']['idade_dias'], 40)
        self.assertEqual(case['variaveis']['duracao_horas'], 48)

    def test_only_explicit_temperature_context_is_accepted(self):
        for text in ['temperatura corporal: 40,2', '40.2 °C', 'febre de 40,2']:
            with self.subTest(text=text):
                self.assertEqual(extract_clinical_case(text)['variaveis']['temperatura_corporal_c'], 40.2)
        self.assertIsNone(extract_clinical_case('animal com 40 kg')['variaveis']['temperatura_corporal_c'])

    def test_last_temperature_measurement_updates_case(self):
        case = extract_clinical_case('temperatura 41 °C\nAgora temperatura 38 °C')
        self.assertEqual(case['variaveis']['temperatura_corporal_c'], 38)
        self.assertEqual(case['sintomas'], [])

    def test_negated_attribute_does_not_negate_separate_symptom(self):
        case = extract_clinical_case('fêmea não gestante com tosse')
        self.assertEqual([s.nome for s in case['sintomas']], ['Tosse'])
        self.assertEqual(case['variaveis']['genero'], 'Fêmea')
        self.assertEqual(case['variaveis']['estado_reprodutivo'], '')
        self.assertEqual(case['variaveis_negadas'], {'estado_reprodutivo': 'Gestante'})

    def test_negated_and_uncertain_measurements_do_not_create_fever(self):
        for text in ['temperatura não é 40 °C', 'talvez temperatura 40 °C']:
            with self.subTest(text=text):
                case = extract_clinical_case(text)
                self.assertIsNone(case['variaveis']['temperatura_corporal_c'])
                self.assertEqual(case['sintomas'], [])

    def test_negation_and_uncertainty_span_coordinated_lists(self):
        case = extract_clinical_case('sem febre, tosse ou diarreia')
        self.assertEqual(case['sintomas'], [])
        self.assertEqual(set(case['sintomas_negados']), {'Febre', 'Tosse', 'Diarreia'})
        case = extract_clinical_case('talvez febre, tosse ou diarreia; apresenta dispneia')
        self.assertEqual(set(case['sintomas_incertos']), {'Febre', 'Tosse', 'Diarreia'})
        self.assertEqual([s.nome for s in case['sintomas']], ['Dispneia'])

    def test_last_attribute_mention_and_its_certainty_win(self):
        case = extract_clinical_case('animal na creche. Correção: está em terminação com tosse')
        self.assertEqual(case['variaveis']['fase_reprodutiva'], 'Terminação')
        case = extract_clinical_case('gestante. Correção: talvez esteja lactante; tosse')
        self.assertEqual(case['variaveis']['estado_reprodutivo'], '')
        self.assertEqual(case['variaveis_incertas']['estado_reprodutivo'], 'Lactante')

    def test_positive_alias_does_not_negate_next_sign(self):
        case = extract_clinical_case('sem apetite e tosse')
        self.assertEqual({s.nome for s in case['sintomas']}, {'Perda de apetite', 'Tosse'})
        case = extract_clinical_case('não apenas tosse, mas febre')
        self.assertEqual({s.nome for s in case['sintomas']}, {'Febre', 'Tosse'})

    def test_hyphenated_symptom_survives_text_conversion(self):
        Sintoma.objects.create(nome='Diarreia muco-hemorrágica')
        for text in ['diarreia muco hemorragica', 'diarreia muco-hemorrágica']:
            self.assertIn('Diarreia muco-hemorrágica', [s.nome for s in extract_clinical_case(text)['sintomas']])

    def test_specific_symptom_does_not_overwrite_independent_general_sign(self):
        for text in ['febre; sem febre alta', 'febre; talvez febre alta']:
            with self.subTest(text=text):
                case = extract_clinical_case(text)
                self.assertEqual([s.nome for s in case['sintomas']], ['Febre'])
                self.assertNotIn('Febre', case['sintomas_negados'])
                self.assertNotIn('Febre', case['sintomas_incertos'])
        case = extract_clinical_case('febre alta')
        self.assertEqual([s.nome for s in case['sintomas']], ['Febre alta'])

    def test_missing_information_marker_is_not_a_clinical_sign(self):
        Sintoma.objects.create(nome='Não informado no documento')
        case = extract_clinical_case('Não informado no documento')
        self.assertEqual(case['sintomas'], [])
        self.assertEqual(case['sintomas_negados'], [])


class KnowledgeEngineRegressionTests(TestCase):
    def setUp(self):
        self.tosse = Sintoma.objects.create(nome='Tosse')
        self.febre = Sintoma.objects.create(nome='Febre')
        self.dispneia = Sintoma.objects.create(nome='Dispneia')
        self.apetite = Sintoma.objects.create(nome='Perda de apetite')
        self.respiratory = Doenca.objects.create(nome='Respiratória')
        self.respiratory.sintomas.set([self.tosse, self.febre, self.dispneia])
        self.other = Doenca.objects.create(nome='Outra')
        self.other.sintomas.set([self.apetite])

    def test_bayes_compares_same_observation_for_all_diseases(self):
        result = MotorBayesiano().inferir('tosse e febre')
        self.assertEqual(result['hipoteses'][0]['id'], self.respiratory.id)
        # Priors iguais: 0,8² / (0,8² + 0,2²).
        self.assertAlmostEqual(result['hipoteses'][0]['score'], 16 / 17, places=6)

    def test_bayes_ignores_unknown_symptoms_and_uses_complement_for_negation(self):
        initial = MotorBayesiano().inferir('tosse')
        uncertain = MotorBayesiano().inferir('tosse. Talvez dispneia')
        self.assertEqual(initial['hipoteses'], uncertain['hipoteses'])
        negative = MotorBayesiano().inferir('tosse; não apresenta febre')
        self.assertAlmostEqual(negative['hipoteses'][0]['score'], 0.5, places=6)

    def test_unknown_catalog_entries_do_not_change_bayes_posterior(self):
        before = MotorBayesiano().inferir('tosse')['hipoteses']
        symptom = Sintoma.objects.create(nome='Icterícia')
        self.respiratory.sintomas.add(symptom)
        self.assertEqual(before, MotorBayesiano().inferir('tosse')['hipoteses'])

    def test_engines_abstain_without_positive_observation(self):
        for engine in [MotorBayesiano(), MotorFuzzy()]:
            self.assertEqual(engine.inferir('animal saudável')['hipoteses'], [])

    def test_engines_respect_limit(self):
        for engine in [MotorBayesiano(), MotorFuzzy()]:
            self.assertLessEqual(len(engine.inferir('tosse; perda de apetite', limite=1)['hipoteses']), 1)
            self.assertEqual(engine.inferir('tosse', limite=0)['hipoteses'], [])

    def test_fuzzy_excludes_zero_support_and_exposes_rule_activations(self):
        result = MotorFuzzy().inferir('tosse e febre')
        self.assertEqual([h['id'] for h in result['hipoteses']], [self.respiratory.id])
        self.assertTrue(result['hipoteses'][0]['regras_fuzzy'])

    def test_uncertain_observation_reduces_fuzzy_support(self):
        confirmed = MotorFuzzy().inferir('tosse')['hipoteses'][0]['score']
        uncertain = MotorFuzzy().inferir('talvez tosse')['hipoteses'][0]['score']
        self.assertGreater(confirmed, uncertain)
        self.assertGreater(uncertain, 0)

    def test_fuzzy_temperature_is_continuous_without_bonus(self):
        disease = Doenca.objects.create(nome='Febril')
        disease.sintomas.add(self.febre)
        low = next(h for h in MotorFuzzy().inferir('temperatura 39,6 °C')['hipoteses'] if h['id'] == disease.id)
        high = next(h for h in MotorFuzzy().inferir('temperatura 39,9 °C')['hipoteses'] if h['id'] == disease.id)
        self.assertLess(low['score'], high['score'])
        self.assertAlmostEqual(low['score'], 0.2, places=6)
        self.assertAlmostEqual(high['score'], 0.8, places=6)

    def test_sugeno_partition_rules_and_weighted_output(self):
        self.assertAlmostEqual(sum(pertinencias(0.3).values()), 1)
        score, rules = inferir_sugeno(0.75, 0.75)
        # 4 regras com peso 0,25; consequentes 0,5; 0,5; 0,5; 1.
        self.assertAlmostEqual(score, 0.625)
        self.assertEqual(len(rules), 4)
        self.assertAlmostEqual(sum(r['ativacao'] for r in rules), 1)

    def test_scores_do_not_imply_clinical_confidence_or_suitability(self):
        result = MotorBayesiano().inferir('tosse e febre')
        _adicionar_graus_avaliacao(result)
        self.assertEqual(result['avaliacao']['confianca_diagnostica'], 'não estimada')
        self.assertEqual(result['avaliacao']['criterios_modelo']['adequacao_clinica'], 'não avaliada')

    def test_sanchez_uses_max_of_minima_and_exposes_binary_relation(self):
        score, terms = composicao_max_min({'tosse': 0.8, 'febre': 0.4}, {'tosse': 0.3, 'febre': 0.9})
        self.assertAlmostEqual(score, 0.4)
        self.assertEqual(terms, {'tosse': 0.3, 'febre': 0.4})
        result = MotorFuzzySanchez().inferir('tosse; talvez febre')
        self.assertEqual(result['hipoteses'][0]['id'], self.respiratory.id)
        self.assertEqual(result['hipoteses'][0]['score'], 1)
        terms_by_name = {item['sintoma']: item['minimo'] for item in result['hipoteses'][0]['composicao']}
        self.assertEqual(terms_by_name['Febre'], 0.5)
        self.assertEqual(MotorFuzzySanchez().inferir('não apresenta tosse')['hipoteses'], [])

    def test_sanchez_exposes_all_top_ties_before_limiting_output(self):
        self.other.sintomas.add(self.tosse)
        result = MotorFuzzySanchez().inferir('tosse', limite=1)
        self.assertEqual(result['empates_no_maior_grau'], 2)
        self.assertEqual(len(result['hipoteses']), 1)

    def test_bayes_parameters_are_validated_and_use_binary_complements(self):
        result = MotorBayesiano(0.9, 0.1).inferir('tosse')
        self.assertAlmostEqual(result['hipoteses'][0]['score'], 0.9)
        for values in [(1, 0.2), (0.2, 0.8), (0.8, 0)]:
            with self.assertRaises(ValueError):
                MotorBayesiano(*values)

    def test_missing_information_disease_does_not_enter_bayesian_prior(self):
        before = MotorBayesiano().inferir('tosse')['hipoteses']
        missing = Doenca.objects.create(nome='Sem documentação')
        missing.sintomas.add(Sintoma.objects.create(nome='Não informado no documento'))
        self.assertEqual(MotorBayesiano().inferir('tosse')['hipoteses'], before)
        for engine in [MotorBayesiano(), MotorFuzzy(), MotorFuzzySanchez()]:
            self.assertEqual(engine.inferir('Não informado no documento')['hipoteses'], [])
