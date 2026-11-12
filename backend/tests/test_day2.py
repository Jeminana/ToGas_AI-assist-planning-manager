"""Journal retry, segmentation and review regressions. No real model or API calls."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import date
from pathlib import Path
import sqlite3
import json
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
import ai
import main


class Day2JournalTests(unittest.TestCase):
    def setUp(self):
        self.resources = ExitStack()
        self.addCleanup(self.resources.close)
        directory = self.resources.enter_context(TemporaryDirectory(prefix='togas-day2-', dir=Path(__file__).resolve().parents[2]))
        self.resources.enter_context(patch.object(main, 'DB', Path(directory) / 'test.db'))
        self.resources.enter_context(patch.dict('os.environ', {'TOGAS_AI_MODE': 'mock'}))
        self.resources.enter_context(patch.object(ai, 'JevDecision', side_effect=AssertionError('No live calls allowed')))
        self.client = self.resources.enter_context(TestClient(main.app))

    def test_repeated_save_request_returns_the_same_entry(self):
        body = {'text': 'Meet my friend tomorrow.', 'request_id': str(uuid4())}
        first = self.client.post('/api/journals', json=body)
        second = self.client.post('/api/journals', json=body)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.json(), second.json())
        self.assertEqual(len(self.client.get('/api/journals').json()), 1)

    def test_simultaneous_retries_save_only_one_entry(self):
        body = {'text': 'Read notes.', 'request_id': str(uuid4())}
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.client.post('/api/journals', json=body), range(4)))
        self.assertTrue(all(response.status_code == 201 for response in results))
        self.assertEqual(len({response.json()['id'] for response in results}), 1)
        self.assertEqual(len(self.client.get('/api/journals').json()), 1)

    def test_reusing_a_save_request_for_different_content_is_rejected(self):
        token = str(uuid4())
        original = {'text': 'Original journal.', 'request_id': token}
        first = self.client.post('/api/journals', json=original).json()
        response = self.client.post('/api/journals', json={'text': 'Different journal.', 'request_id': token})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.client.get('/api/journals').json(), [first])
        self.assertEqual(self.client.post('/api/journals', json=original).json(), first)

    def test_intentionally_new_identical_entries_remain_possible(self):
        for _ in range(2):
            self.assertEqual(self.client.post('/api/journals', json={'text': 'Same thoughts.', 'request_id': str(uuid4())}).status_code, 201)
        self.assertEqual(len(self.client.get('/api/journals').json()), 2)

    def test_save_tokens_are_validated_and_not_exposed_in_history(self):
        self.assertEqual(self.client.post('/api/journals', json={'text': 'Read.', 'request_id': 'invalid'}).status_code, 422)
        response = self.client.post('/api/journals', json={'text': 'Read.', 'request_id': str(uuid4())})
        self.assertNotIn('request_id', response.json())
        self.assertNotIn('request_id', self.client.get('/api/search?q=Read').json()['journals'][0])
        self.assertEqual(self.client.post('/api/ai/analyze', json={'text': 'Read.', 'request_id': str(uuid4())}).status_code, 422)

    def test_pipeline_preserves_source_and_explains_review_flags(self):
        result = self.client.post('/api/ai/analyze', json={'text': 'Visit Dr. Kim tomorrow. Read chapter 3.5.', 'reference_date': '2026-11-12'}).json()
        self.assertEqual(result['segments_processed'], 2)
        self.assertEqual(len(result['proposals']), 2)
        self.assertEqual(result['proposals'][0]['source_text'], 'Visit Dr. Kim tomorrow.')
        self.assertEqual(result['proposals'][0]['due_date'], '2026-11-13')
        self.assertTrue(result['proposals'][0]['review_reasons'])
        self.assertEqual(self.client.get('/api/tasks').json(), [])


class Day2SegmentationTests(unittest.TestCase):
    def test_common_abbreviations_numbers_and_urls_are_kept(self):
        cases = [
            ('Meet Dr. Kim tomorrow. Buy milk.', ['Meet Dr. Kim tomorrow.', 'Buy milk.']),
            ('Email Prof. Park today. Read notes.', ['Email Prof. Park today.', 'Read notes.']),
            ('Read chapter 3.5. Visit https://example.com.', ['Read chapter 3.5.', 'Visit https://example.com.']),
            ('Try e.g. Python exercises. Submit homework.', ['Try e.g. Python exercises.', 'Submit homework.']),
            ('Meet at 9 a.m. tomorrow. Buy milk.', ['Meet at 9 a.m. tomorrow.', 'Buy milk.']),
            ('내일 과제 제출。친구 만나기！', ['내일 과제 제출。', '친구 만나기！']),
            ('1. Read notes.\n2) Buy milk; Clean room.', ['Read notes.', 'Buy milk', 'Clean room.']),
            ('I need to study and i should clean my room.', ['I need to study', 'i should clean my room.']),
            ('Buy bread and milk.', ['Buy bread and milk.']),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(ai.segment(text), expected)

    def test_long_suggestion_keeps_original_source_and_explains_shortening(self):
        text = 'Read ' + 'notes ' * 50 + 'tomorrow.'
        with patch.dict('os.environ', {'TOGAS_AI_MODE': 'mock'}):
            proposal = ai.analyze(text, date(2026, 11, 12))[0]
        self.assertEqual(len(proposal['title']), 250)
        self.assertEqual(proposal['source_text'], text)
        self.assertEqual(proposal['due_date'], '2026-11-13')
        self.assertTrue(any('shortened' in reason for reason in proposal['review_reasons']))

    def test_normalized_fallbacks_are_explained(self):
        answers = {'answers': {'actionable': {'noul': 0.9}, 'category': {'choice': 'invalid'}, 'urgency': {'score': 99}}}
        with patch.dict('os.environ', {'TOGAS_AI_MODE': 'local'}), patch.object(ai, 'get_model') as model:
            model.return_value.decide.return_value = answers
            proposal = ai.analyze('Read notes.')[0]
        self.assertEqual(proposal['category'], 'other')
        self.assertEqual(proposal['urgency_score'], 1)
        self.assertTrue(any('category was unavailable' in reason for reason in proposal['review_reasons']))
        self.assertTrue(any('urgency was unavailable' in reason for reason in proposal['review_reasons']))


class Day2MigrationTests(unittest.TestCase):
    def test_existing_journals_survive_upgrade_and_retries_across_restarts(self):
        with TemporaryDirectory(prefix='togas-day2-migration-', dir=Path(__file__).resolve().parents[2]) as directory:
            path = Path(directory) / 'old.db'
            db = sqlite3.connect(path)
            with db:
                db.execute('CREATE TABLE journals (id INTEGER PRIMARY KEY, content TEXT NOT NULL, created_at TEXT NOT NULL)')
                db.execute('INSERT INTO journals VALUES (1, "Existing journal.", "2026-11-12")')
            db.close()
            body = {'text': 'New journal.', 'request_id': str(uuid4())}
            ids = []
            for _ in range(2):
                with patch.object(main, 'DB', path), TestClient(main.app) as client:
                    ids.append(client.post('/api/journals', json=body).json()['id'])
                    self.assertEqual(len(client.get('/api/journals').json()), 2)
                    self.assertTrue(any(entry['content'] == 'Existing journal.' for entry in client.get('/api/journals').json()))
            self.assertEqual(ids[0], ids[1])


class Day2EvaluationTests(unittest.TestCase):
    def test_prepared_mixed_journals_run_without_any_api_calls(self):
        from evaluate_journals import evaluate_journals
        cases = json.loads((Path(__file__).resolve().parents[1] / 'evaluation/day2-journals.json').read_text(encoding='utf-8'))
        for case in cases:
            self.assertEqual(ai.segment(case['text']), [row['source_text'] for row in case['expected']])
        with patch.dict('os.environ', {'TOGAS_AI_MODE': 'mock'}), patch.object(ai, 'JevDecision', side_effect=AssertionError('No API allowed')):
            rows = evaluate_journals(cases)
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row['error'] is None for row in rows))
        self.assertTrue(all(row['result']['request_count'] == 0 for row in rows))

    def test_mixed_journal_evaluation_stops_after_a_service_error(self):
        import evaluate_journals
        case = {'id': 'example', 'text': 'Read.', 'reference_date': '2026-11-12', 'expected': []}
        with patch.object(evaluate_journals, 'analyze_result', side_effect=RuntimeError('No service')) as call:
            rows = evaluate_journals.evaluate_journals([case, case])
        self.assertEqual(call.call_count, 1)
        self.assertEqual(len(rows), 1)
        self.assertIsNotNone(rows[0]['error'])
