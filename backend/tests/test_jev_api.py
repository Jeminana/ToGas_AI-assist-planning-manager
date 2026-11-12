"""Hosted adapter checks. Every HTTP request uses MockTransport, never a real key."""
from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx2 as httpx
from fastapi.testclient import TestClient
import ai
import main
from jev_api import DecisionCache, JevDecision, JevError, JEV_ENDPOINT

REFERENCE = date(2026, 11, 12)
TEST_KEY = 'synthetic-test-key-not-a-real-credential'


def response_for(request):
    body = json.loads(request.content)
    answers = {}
    for key, question in body['questions'].items():
        if question['type'] == 'noul':
            answers[key] = {'type': 'noul', 'noul': 0.95 if key.startswith('s0_') else 0.1}
        elif question['type'] == 'choice':
            answers[key] = {'type': 'choice', 'choice': 'study', 'confidence': 0.9}
        else:
            answers[key] = {'type': 'score', 'score': 2.25, 'confidence': 0.85}
    return {'model': 'jev-test-fixture', 'answers': answers, 'usage': {'input_tokens': 300, 'output_tokens': 20}}


class JevAdapterTests(unittest.TestCase):
    def adapter(self, handler, **kwargs):
        return JevDecision(api_key=TEST_KEY, transport=httpx.MockTransport(handler), cache=DecisionCache(), **kwargs)

    def test_all_segments_and_question_types_share_one_post(self):
        calls = []
        def handler(request):
            calls.append(request)
            self.assertEqual(str(request.url), JEV_ENDPOINT)
            self.assertEqual(request.method, 'POST')
            self.assertEqual(request.headers['Authorization'], f'Bearer {TEST_KEY}')
            self.assertNotIn(TEST_KEY, request.content.decode())
            body = json.loads(request.content)
            self.assertEqual(body['model'], 'jev-latest')
            self.assertEqual(len(body['questions']), 6)
            self.assertIn('segment s1', body['questions']['s1_category']['instructions'])
            self.assertEqual(body['state']['reference_date'], '2026-11-12')
            return httpx.Response(200, json=response_for(request))
        result = self.adapter(handler).decide_many(['Read tomorrow.', 'I feel tired.'], ai.QUESTIONS, REFERENCE)
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(result['decisions']), 2)
        self.assertEqual(result['request_count'], 1)
        self.assertFalse(result['cached'])

    def test_successful_identical_requests_are_cached_and_copies_are_independent(self):
        calls = []
        def handler(request):
            calls.append(request)
            return httpx.Response(200, json=response_for(request))
        adapter = self.adapter(handler)
        first = adapter.decide_many(['Read tomorrow.'], ai.QUESTIONS, REFERENCE)
        first['decisions'][0]['answers']['category']['choice'] = 'mutated'
        second = adapter.decide_many(['Read tomorrow.'], ai.QUESTIONS, REFERENCE)
        self.assertEqual(len(calls), 1)
        self.assertEqual(second['request_count'], 0)
        self.assertTrue(second['cached'])
        self.assertEqual(second['decisions'][0]['answers']['category']['choice'], 'study')

    def test_cache_separates_credentials_model_text_date_and_questions(self):
        calls = []
        def handler(request):
            calls.append(request)
            return httpx.Response(200, json=response_for(request))
        transport, cache = httpx.MockTransport(handler), DecisionCache()
        def adapter(key=TEST_KEY, model='jev-latest'):
            return JevDecision(api_key=key, model=model, transport=transport, cache=cache)
        adapter().decide_many(['Read.'], ai.QUESTIONS, REFERENCE)
        adapter(key='another-synthetic-key').decide_many(['Read.'], ai.QUESTIONS, REFERENCE)
        adapter(model='jev-preview').decide_many(['Read.'], ai.QUESTIONS, REFERENCE)
        adapter().decide_many(['Different.'], ai.QUESTIONS, REFERENCE)
        adapter().decide_many(['Read.'], ai.QUESTIONS, date(2026, 11, 13))
        changed = deepcopy(ai.QUESTIONS)
        changed['actionable']['instructions'] += ' Changed.'
        adapter().decide_many(['Read.'], changed, REFERENCE)
        self.assertEqual(len(calls), 6)

    def test_expired_cache_makes_one_new_request(self):
        calls = []
        def handler(request):
            calls.append(request)
            return httpx.Response(200, json=response_for(request))
        adapter = JevDecision(api_key=TEST_KEY, transport=httpx.MockTransport(handler), cache=DecisionCache(ttl=0))
        for _ in range(2):
            adapter.decide_many(['Read.'], ai.QUESTIONS, REFERENCE)
        self.assertEqual(len(calls), 2)

    def test_http_failures_and_redirects_never_retry_or_echo_upstream_data(self):
        for status in [302, 401, 403, 422, 429, 500, 529]:
            with self.subTest(status=status):
                calls = []
                def handler(request):
                    calls.append(request)
                    return httpx.Response(status, headers={'Location': 'https://example.invalid/leak'}, text=TEST_KEY)
                with self.assertRaises(JevError) as caught:
                    self.adapter(handler).decide_many(['Read.'], ai.QUESTIONS, REFERENCE)
                self.assertEqual(caught.exception.status, status)
                self.assertNotIn(TEST_KEY, str(caught.exception))
                self.assertEqual(len(calls), 1)

    def test_timeout_and_connection_errors_are_sanitized_without_retries(self):
        for exception in [httpx.ReadTimeout, httpx.ConnectError]:
            with self.subTest(exception=exception):
                calls = []
                def handler(request):
                    calls.append(request)
                    raise exception(TEST_KEY)
                with self.assertRaises(JevError) as caught:
                    self.adapter(handler).decide_many(['Read.'], ai.QUESTIONS, REFERENCE)
                self.assertNotIn(TEST_KEY, str(caught.exception))
                self.assertEqual(len(calls), 1)

    def test_invalid_json_missing_answers_wrong_types_and_nonfinite_probabilities(self):
        for kind in ['json', 'missing', 'type', 'nan', 'model']:
            with self.subTest(kind=kind):
                def handler(request):
                    body = response_for(request)
                    if kind == 'json':
                        return httpx.Response(200, text='not json')
                    if kind == 'missing': del body['answers']['s0_actionable']
                    if kind == 'type': body['answers']['s0_actionable']['type'] = 'choice'
                    if kind == 'nan': body['answers']['s0_actionable']['noul'] = 'NaN'
                    if kind == 'model': body['model'] = TEST_KEY
                    return httpx.Response(200, json=body)
                with self.assertRaises(JevError):
                    self.adapter(handler).decide_many(['Read.'], ai.QUESTIONS, REFERENCE)

    def test_missing_key_empty_input_and_segment_cap_do_not_make_requests(self):
        with self.assertRaises(JevError): JevDecision(api_key='')
        calls = []
        adapter = self.adapter(lambda request: calls.append(request))
        self.assertEqual(adapter.decide_many([], ai.QUESTIONS, REFERENCE)['request_count'], 0)
        with self.assertRaises(JevError): adapter.decide_many(['Read.'] * 16, ai.QUESTIONS, REFERENCE)
        self.assertEqual(calls, [])

    def test_full_api_pipeline_reports_metadata_and_never_autosaves(self):
        def handler(request): return httpx.Response(200, json=response_for(request))
        adapter = self.adapter(handler)
        with TemporaryDirectory(prefix='togas-jev-test-', dir=Path(__file__).resolve().parents[2]) as directory:
            with patch.object(main, 'DB', Path(directory) / 'test.db'), patch.dict('os.environ', {'TOGAS_AI_MODE': 'jev'}), patch.object(ai, 'JevDecision', return_value=adapter), TestClient(main.app) as client:
                body = {'text': 'Read notes tomorrow. I feel tired.', 'reference_date': '2026-11-12'}
                first = client.post('/api/ai/analyze', json=body)
                self.assertEqual(first.status_code, 200, first.text)
                result = first.json()
                self.assertEqual(result['provider'], 'jev')
                self.assertEqual(result['model'], 'jev-test-fixture')
                self.assertEqual(result['usage']['input_tokens'], 300)
                self.assertEqual(len(result['proposals']), 1)
                self.assertEqual(result['proposals'][0]['due_date'], '2026-11-13')
                self.assertEqual(result['proposals'][0]['urgency_score'], 2.25)
                self.assertEqual(client.get('/api/tasks').json(), [])
                self.assertEqual(client.post('/api/ai/analyze', json=body).json()['request_count'], 0)
                self.assertNotIn(TEST_KEY, first.text)

    def test_upstream_auth_failure_is_useful_and_does_not_fallback_to_mock(self):
        adapter = self.adapter(lambda request: httpx.Response(401, text=TEST_KEY))
        with TemporaryDirectory(prefix='togas-jev-test-', dir=Path(__file__).resolve().parents[2]) as directory:
            with patch.object(main, 'DB', Path(directory) / 'test.db'), patch.dict('os.environ', {'TOGAS_AI_MODE': 'jev'}), patch.object(ai, 'JevDecision', return_value=adapter), TestClient(main.app) as client:
                response = client.post('/api/ai/analyze', json={'text': 'Read notes.'})
                self.assertEqual(response.status_code, 503)
                self.assertIn('HTTP 401', response.json()['detail'])
                self.assertNotIn(TEST_KEY, response.text)
                self.assertNotIn('proposals', response.json())


class LiveEvaluationBudgetTests(unittest.TestCase):
    def test_live_evaluation_stops_at_first_service_failure(self):
        import evaluate
        examples = [{'text': 'Read.', 'actionable': True, 'category': 'study', 'due_date': None}] * 3
        with patch.dict('os.environ', {'TOGAS_AI_MODE': 'jev'}), patch.object(evaluate, 'analyze', side_effect=JevError('Rate limited', status=429)) as call:
            metrics, rows = evaluate.evaluate(examples, REFERENCE)
        self.assertEqual(call.call_count, 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(metrics['errors'], 1)

    def test_mock_evaluation_continues_without_external_requests(self):
        import evaluate
        examples = [{'text': 'I feel tired.', 'actionable': False}] * 2
        with patch.dict('os.environ', {'TOGAS_AI_MODE': 'mock'}), patch.object(evaluate, 'analyze', side_effect=[ValueError('Local failure'), []]) as call:
            metrics, rows = evaluate.evaluate(examples, REFERENCE)
        self.assertEqual(call.call_count, 2)
        self.assertEqual(len(rows), 2)
        self.assertEqual(metrics['errors'], 1)
