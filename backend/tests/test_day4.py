"""Day 4 hosted contract, extraction metrics and conservative language rules."""
from contextlib import ExitStack
from datetime import date
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
import httpx2 as httpx
import ai
import main
from evaluate import evaluate_extraction
from evaluate_journals import evaluate_journals
from jev_api import DecisionCache, JevDecision
from segmentation import candidates, segment

REFERENCE = date(2026, 11, 14)
DATASET = Path(__file__).resolve().parents[1] / 'evaluation/day4-journals.json'


class Day4LanguageTests(unittest.TestCase):
    def test_dataset_labels_and_required_examples(self):
        rows = json.loads(DATASET.read_text(encoding='utf-8'))
        self.assertEqual(len(rows), 40)
        self.assertEqual(len({row['id'] for row in rows}), 40)
        with patch.dict('os.environ', {'TOGAS_AI_MODE': 'mock'}), patch.object(ai, 'JevDecision', side_effect=AssertionError('No live calls')):
            for row in rows:
                self.assertEqual(row['expected_count'], len(row['expected_actions']))
                for target in row['expected_actions']:
                    self.assertIn(target['action_span'], row['text'])
            for row in rows[:12]:
                with self.subTest(id=row['id']):
                    result = ai.analyze(row['text'], REFERENCE)
                    self.assertEqual([item['action_span'] for item in result], [item['action_span'] for item in row['expected_actions']])
                    self.assertTrue(all(item['needs_review'] and item['source_text'] in row['text'] for item in result))

    def test_korean_shared_objects_negation_and_completion_are_not_split(self):
        for text in ['빵하고 우유를 사야 해.', '친구하고 과제를 제출해야 한다.', '내일 과제를 제출하고 싶지만 하지 않아도 돼.', '과제를 제출하고 친구를 이미 만났다.']:
            with self.subTest(text=text):
                self.assertEqual(segment(text), [text])
        for text in ['과제를 제출하고 친구를 만나지 않아도 돼.', '오늘 너무 피곤하다.']:
            self.assertFalse(ai.is_mock_action(text))

    def test_negation_scope_resets_only_for_an_independent_subject(self):
        with patch.dict('os.environ', {'TOGAS_AI_MODE': 'mock'}):
            self.assertEqual(ai.analyze('I will not buy milk and clean my room.', REFERENCE), [])
            result = ai.analyze('I finished my report but I need to buy groceries.', REFERENCE)
            self.assertEqual([row['title'] for row in result], ['I need to buy groceries.'])
            self.assertEqual(len(ai.analyze('I feel tired but I should call my mother.', REFERENCE)), 1)

    def test_unpunctuated_ambiguous_text_is_preserved_with_review_reason(self):
        text = 'meet friend cook dinner'
        result = candidates(text)
        self.assertEqual([row.text for row in result], [text])
        self.assertTrue(any('clear clause boundary' in reason for reason in result[0].review_reasons))

    def test_repeated_intentions_stay_separate_but_are_flagged(self):
        with patch.dict('os.environ', {'TOGAS_AI_MODE': 'mock'}):
            result = ai.analyze('Buy milk. Buy milk.', REFERENCE)
        self.assertEqual(len(result), 2)
        self.assertTrue(any('more than once' in reason for reason in result[1]['review_reasons']))

    def test_protected_quotes_and_original_sources_remain_intact(self):
        text = 'Write "buy milk and clean my room" tomorrow.'
        self.assertEqual(segment(text), [text])
        text = '내일 과제를 제출하고 친구를 만나야 해.'
        self.assertTrue(all(row.source_text == text and row.review_reasons for row in candidates(text)))


class Day4EvaluationTests(unittest.TestCase):
    def test_one_to_one_spans_do_not_hide_extra_or_merged_tasks(self):
        row = {'id': 'example', 'text': 'Read notes and cook dinner.', 'expected_count': 2, 'expected_actions': [
            {'action_span': 'Read notes', 'category': 'study', 'due_date': None}, {'action_span': 'cook dinner.', 'category': 'personal', 'due_date': None}], 'manual_review_required': True}
        predicted = {'proposals': [{'title': 'Read notes', 'category': 'study', 'needs_review': True}] * 2}
        with patch('evaluate.analyze_result', return_value=predicted):
            metrics, _ = evaluate_extraction([row], REFERENCE)
        self.assertEqual((metrics['true_positives'], metrics['false_positives'], metrics['false_negatives']), (1, 1, 1))
        self.assertEqual(metrics['extraction_f1'], 0.5)
        # Count correctness alone cannot assert extraction quality.
        self.assertEqual(metrics['exact_task_count_accuracy'], 1)

    def test_multi_task_same_source_and_duplicates_are_not_collapsed(self):
        row = {'id': 'example', 'text': 'Buy milk. Buy milk.', 'expected_count': 2, 'expected_actions': [{'action_span': 'Buy milk.', 'category': 'personal', 'due_date': None}] * 2, 'manual_review_required': True}
        with patch.dict('os.environ', {'TOGAS_AI_MODE': 'mock'}):
            metrics, _ = evaluate_extraction([row], REFERENCE)
            cases = [{'id': 'example', 'text': 'Buy milk and clean my room.', 'reference_date': REFERENCE.isoformat(), 'expected': [
                {'source_text': 'Buy milk and clean my room.', 'action_span': span, 'actionable': True, 'category': 'personal', 'due_date': None} for span in ['Buy milk', 'clean my room.']]}]
            results = evaluate_journals(cases)
        self.assertEqual(metrics['task_recall'], 1)
        self.assertTrue(all(check['actionability_matches'] for check in results[0]['checks']))

    def test_empty_evaluation_and_classification_vs_segmentation_diagnostics(self):
        metrics, rows = evaluate_extraction([], REFERENCE)
        self.assertEqual((metrics['examples'], rows), (0, []))
        example = {'id': 'example', 'text': 'Read notes.', 'expected_count': 1, 'expected_actions': [{'action_span': 'Read notes.'}], 'manual_review_required': True}
        with patch('evaluate.analyze_result', return_value={'proposals': []}):
            metrics, _ = evaluate_extraction([example], REFERENCE)
        self.assertEqual(metrics['segmentation_missing_action_spans'], 0)
        self.assertEqual(metrics['classification_missing_action_spans'], 1)

    def test_live_evaluation_stops_after_any_error_without_retries(self):
        example = {'id': 'example', 'text': 'Read notes.', 'expected_count': 0, 'expected_actions': [], 'manual_review_required': False}
        with patch.dict('os.environ', {'TOGAS_AI_MODE': 'jev'}), patch('evaluate.analyze_result', side_effect=ValueError('invalid model output')) as call:
            metrics, rows = evaluate_extraction([example, example], REFERENCE)
        self.assertEqual(call.call_count, 1)
        self.assertEqual((metrics['errors'], len(rows)), (1, 1))


class Day4HostedPipelineTests(unittest.TestCase):
    def setUp(self):
        self.resources = ExitStack()
        self.addCleanup(self.resources.close)
        directory = self.resources.enter_context(TemporaryDirectory(prefix='togas-day4-', dir=Path(__file__).resolve().parents[2]))
        self.resources.enter_context(patch.object(main, 'DB', Path(directory) / 'test.db'))
        self.client = self.resources.enter_context(TestClient(main.app))

    def test_hosted_normalization_metadata_failure_recovery_and_explicit_approval(self):
        calls = []
        def handler(request):
            payload = json.loads(request.content)
            calls.append(payload)
            self.assertEqual(set(payload), {'model', 'state', 'questions'})
            answers = {}
            for key, question in payload['questions'].items():
                kind = question['type']
                answers[key] = {'type': kind, **({'noul': 0.72 if key.startswith('s0_') else 0.1} if kind == 'noul' else {'choice': 'invalid', 'confidence': 0.99} if kind == 'choice' else {'score': 99})}
            return httpx.Response(200, json={'model': 'jev-fixture-only', 'answers': answers, 'usage': {'input_tokens': 123, 'output_tokens': 45}, 'due_date': '2099-01-01'})
        adapter = JevDecision(api_key='synthetic-only', transport=httpx.MockTransport(handler), cache=DecisionCache())
        text = 'Read notes tomorrow. I feel tired.'
        journal = self.client.post('/api/journals', json={'text': text}).json()
        with patch.dict('os.environ', {'TOGAS_AI_MODE': 'jev'}), patch.object(ai, 'JevDecision', return_value=adapter):
            response = self.client.post('/api/ai/analyze', json={'text': text, 'journal_id': journal['id'], 'reference_date': REFERENCE.isoformat()})
            self.assertEqual(response.status_code, 200)
            result = response.json()
            self.assertEqual(result['model'], 'jev-fixture-only')
            self.assertEqual(result['usage'], {'input_tokens': 123, 'output_tokens': 45})
            self.assertGreaterEqual(result['analysis_latency_ms'], 0)
            proposal = result['proposals'][0]
            self.assertEqual((proposal['category'], proposal['urgency_score'], proposal['due_date']), ('other', 1, '2026-11-15'))
            self.assertIsNone(proposal['category_confidence'])
            self.assertIsNone(proposal['urgency_confidence'])
            self.assertEqual(proposal['action_probability'], 0.72)
            self.assertTrue(proposal['needs_review'])
            self.assertEqual(self.client.get('/api/tasks').json(), [])
            body = {key: proposal[key] for key in ['title', 'category', 'urgency_score', 'due_date']}
            body.update(journal_id=journal['id'], request_id=str(uuid4()))
            approved = self.client.post('/api/tasks', json=body).json()
            self.assertEqual(self.client.post('/api/tasks', json=body).json(), approved)
            failing = JevDecision(api_key='synthetic-only', transport=httpx.MockTransport(lambda request: httpx.Response(503, text='upstream-private-body')), cache=DecisionCache())
            with patch.object(ai, 'JevDecision', return_value=failing), patch.object(ai, 'MockDecision', side_effect=AssertionError('No silent fallback')):
                failure = self.client.post('/api/ai/analyze', json={'text': text, 'journal_id': journal['id']})
            self.assertEqual(failure.status_code, 503)
            self.assertNotIn('upstream-private-body', failure.text)
            self.assertEqual(self.client.get('/api/tasks').json(), [approved])
            self.assertEqual(self.client.get('/api/journals').json(), [journal])
        self.assertEqual(len(calls), 1)

    def test_missing_confidence_is_not_fabricated(self):
        answer = {'answers': {'actionable': {'noul': 0.9}, 'category': {'choice': 'study'}, 'urgency': {'score': 2}}}
        with patch.dict('os.environ', {'TOGAS_AI_MODE': 'local'}), patch.object(ai, 'get_model') as model:
            model.return_value.decide.return_value = answer
            proposal = ai.analyze('Read notes.', REFERENCE)[0]
        self.assertEqual((proposal['category'], proposal['urgency_score']), ('study', 2))
        self.assertIsNone(proposal['category_confidence'])
        self.assertIsNone(proposal['urgency_confidence'])
        self.assertTrue(proposal['needs_review'])

    def test_plan_from_now_uses_fixed_seoul_clock_and_preserves_confirmed_tasks(self):
        self.client.post('/api/tasks', json={'title': 'Confirmed', 'scheduled_start': '2026-11-14T09:00', 'estimated_minutes': 30})
        self.client.post('/api/tasks', json={'title': 'Short', 'estimated_minutes': 10})
        self.client.post('/api/tasks', json={'title': 'Longer', 'estimated_minutes': 30})
        self.client.put('/api/availability', json={'date': '2026-11-14', 'windows': [{'start': '09:00', 'end': '10:00'}], 'max_tasks': 5})
        with patch.object(main, 'utcnow', return_value='2026-11-14T00:45:20+00:00'):
            result = self.client.post('/api/planning/propose', json={'date': '2026-11-14', 'plan_from_now': True}).json()
            full_day = self.client.post('/api/planning/propose', json={'date': '2026-11-14'}).json()
        self.assertEqual(result['planning_from'], '2026-11-14T09:46:00')
        self.assertEqual(result['placements'][0]['start'], '2026-11-14T09:46:00')
        self.assertEqual(result['confirmed'][0]['start'], '2026-11-14T09:00:00')
        self.assertNotIn('outside_availability', [row['code'] for row in result['conflicts']])
        self.assertTrue(any(row['code'] == 'no_remaining_window' for row in result['unscheduled']))
        self.assertEqual(full_day['placements'][0]['start'], '2026-11-14T09:30:00')

    def test_plan_from_now_ignores_future_days_and_handles_the_last_minute(self):
        self.client.post('/api/tasks', json={'title': 'One minute', 'estimated_minutes': 1})
        for day in ['2026-11-14', '2026-11-15']:
            self.client.put('/api/availability', json={'date': day, 'windows': [{'start': '09:00', 'end': '23:59'}], 'max_tasks': 5})
        with patch.object(main, 'utcnow', return_value='2026-11-14T14:59:30+00:00'):
            today = self.client.post('/api/planning/propose', json={'date': '2026-11-14', 'plan_from_now': True}).json()
            future = self.client.post('/api/planning/propose', json={'date': '2026-11-15', 'plan_from_now': True}).json()
        self.assertEqual(today['placements'], [])
        self.assertEqual(today['unscheduled'][0]['code'], 'no_remaining_window')
        self.assertEqual(future['placements'][0]['start'], '2026-11-15T09:00:00')
        self.assertIsNone(future['planning_from'])
        self.assertEqual(self.client.post('/api/planning/propose', json={'date': '2026-11-14', 'plan_from_now': 'true'}).status_code, 422)

    def test_from_now_confirmation_rejects_passed_starts_but_preserves_confirmed_retries(self):
        self.client.post('/api/tasks', json={'title': 'Short', 'estimated_minutes': 10})
        self.client.put('/api/availability', json={'date': '2026-11-14', 'windows': [{'start': '09:00', 'end': '10:00'}], 'max_tasks': 5})
        with patch.object(main, 'utcnow', return_value='2026-11-14T00:45:20+00:00'):
            old = self.client.post('/api/planning/propose', json={'date': '2026-11-14', 'plan_from_now': True}).json()
        with patch.object(main, 'utcnow', return_value='2026-11-14T00:46:01+00:00'):
            self.assertEqual(self.client.post('/api/planning/confirm', json={'plan': old}).status_code, 409)
            fresh = self.client.post('/api/planning/propose', json={'date': '2026-11-14', 'plan_from_now': True}).json()
        with patch.object(main, 'utcnow', return_value='2026-11-14T00:46:30+00:00'):
            first = self.client.post('/api/planning/confirm', json={'plan': fresh})
        self.assertEqual(first.status_code, 200)
        with patch.object(main, 'utcnow', return_value='2026-11-14T02:00:00+00:00'):
            retry = self.client.post('/api/planning/confirm', json={'plan': fresh})
        self.assertEqual(retry.json(), first.json())
        self.assertEqual(self.client.get('/api/tasks').json()[0]['scheduled_start'], '2026-11-14T09:47:00')
