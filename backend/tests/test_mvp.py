from contextlib import ExitStack
from datetime import date
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
import ai
import main
from scheduling import dashboard, due_date_from_text, recommend


class MvpApiTests(unittest.TestCase):
    def setUp(self):
        self.resources = ExitStack()
        self.addCleanup(self.resources.close)
        directory = self.resources.enter_context(TemporaryDirectory(prefix='togas-mvp-', dir=Path(__file__).resolve().parents[2]))
        self.resources.enter_context(patch.object(main, 'DB', Path(directory) / 'test.db'))
        self.resources.enter_context(patch.dict('os.environ', {'TOGAS_AI_MODE': 'mock'}))
        self.model = self.resources.enter_context(patch.object(ai, 'get_model', side_effect=AssertionError('No model allowed')))
        self.client = self.resources.enter_context(TestClient(main.app))

    def task(self, **fields):
        response = self.client.post('/api/tasks', json={'title': 'Task', **fields})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_mock_analysis_is_explicit_and_never_saves_proposals(self):
        journal = self.client.post('/api/journals', json={'text': 'I need to finish my NLP assignment tomorrow. I feel tired.'}).json()
        response = self.client.post('/api/ai/extract', json={'text': journal['content'], 'journal_id': journal['id'], 'reference_date': '2026-11-12'})
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result['provider'], 'mock')
        self.assertTrue(result['warnings'])
        self.assertEqual(len(result['proposals']), 1)
        self.assertEqual(result['proposals'][0]['due_date'], '2026-11-13')
        self.assertTrue(result['proposals'][0]['needs_review'])
        self.assertEqual(self.client.get('/api/tasks').json(), [])
        self.model.assert_not_called()
        approved = self.task(title=result['proposals'][0]['title'], journal_id=journal['id'], due_date='2026-11-13')
        self.assertEqual(approved['journal_id'], journal['id'])

    def test_analysis_failure_preserves_journal_and_manual_tasks(self):
        self.task()
        journal = self.client.post('/api/journals', json={'text': 'Read tomorrow.'}).json()
        with patch.dict('os.environ', {'TOGAS_AI_MODE': 'disabled'}):
            response = self.client.post('/api/ai/analyze', json={'text': journal['content'], 'journal_id': journal['id']})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(len(self.client.get('/api/journals').json()), 1)
        self.assertEqual(len(self.client.get('/api/tasks').json()), 1)

    def test_action_phrases_do_not_require_need(self):
        for text in ['Meet my friend tomorrow.', 'Visit the doctor.', 'Attend the lecture.', 'Practice Python.', 'Renew my library card.', 'Pick up groceries.', 'Finish my NLP project.']:
            with self.subTest(text=text):
                result = self.client.post('/api/ai/analyze', json={'text': text}).json()
                self.assertEqual(len(result['proposals']), 1)
                self.assertEqual(result['proposals'][0]['title'], text)
                self.assertTrue(result['proposals'][0]['needs_review'])
        result = self.client.post('/api/ai/analyze', json={'text': 'i need to finish nlp project. meet my friend.'}).json()
        self.assertEqual([proposal['title'] for proposal in result['proposals']], ['i need to finish nlp project.', 'meet my friend.'])
        self.assertEqual(result['proposals'][1]['category'], 'personal')
        for text in ['I feel worried about my friend.', 'I already met my friend.', "I don't need to meet my friend."]:
            with self.subTest(text=text):
                self.assertEqual(self.client.post('/api/ai/analyze', json={'text': text}).json()['proposals'], [])
        self.assertEqual(self.client.get('/api/tasks').json(), [])
        self.model.assert_not_called()

    def test_analysis_segment_limit_is_disclosed(self):
        result = self.client.post('/api/ai/analyze', json={'text': '\n'.join(f'Read chapter {i}.' for i in range(17))}).json()
        self.assertEqual(result['segments_processed'], 15)
        self.assertEqual(result['segments_total'], 17)
        self.assertEqual(len(result['proposals']), 15)
        self.assertIn('17', result['warnings'][0])

    def test_deadline_validation_edit_and_clear(self):
        task = self.task(due_date='2026-11-16')
        url = f'/api/tasks/{task["id"]}'
        for value in ['2026-02-30', '11/16/2026', '20261116', 0, True, '2026-11-16T00:00:00']:
            self.assertEqual(self.client.patch(url, json={'due_date': value}).status_code, 422)
        self.assertEqual(self.client.patch(url, json={'due_date': None}).json()['due_date'], None)
        self.assertEqual(self.client.get('/api/dashboard?today=invalid').status_code, 422)

    def test_complete_reopen_and_today_counts(self):
        task = self.task()
        self.task(title='Future task', due_date='2026-12-01')
        url = f'/api/tasks/{task["id"]}'
        with patch.object(main, 'utcnow', return_value='2026-11-12T02:00:00+00:00'):
            completed = self.client.patch(url, json={'done': True}).json()
        self.assertIsNotNone(completed['completed_at'])
        self.assertEqual(self.client.patch(url, json={'done': True}).json()['completed_at'], completed['completed_at'])
        result = self.client.get('/api/dashboard?today=2026-11-12').json()
        self.assertEqual((result['completed'], result['total']), (1, 1))
        self.assertEqual(self.client.get('/api/dashboard?today=2026-11-13').json()['total'], 0)
        reopened = self.client.patch(url, json={'done': False}).json()
        self.assertIsNone(reopened['completed_at'])
        self.assertEqual(self.client.get('/api/dashboard?today=2026-11-12').json()['completed'], 0)

    def test_search_is_literal_case_insensitive_and_spans_both_types(self):
        self.task(title='NLP 100%_done')
        self.task(title='Unrelated')
        self.client.post('/api/journals', json={'text': 'My nlp notes and 과제'})
        result = self.client.get('/api/search', params={'q': 'nlp'}).json()
        self.assertEqual(len(result['tasks']), 1)
        self.assertEqual(len(result['journals']), 1)
        self.assertEqual(len(self.client.get('/api/tasks', params={'q': '%_'}).json()), 1)
        self.assertEqual(len(self.client.get('/api/journals', params={'q': '과제'}).json()), 1)
        self.assertEqual(self.client.get('/api/search', params={'q': "' OR 1=1 --"}).json(), {'tasks': [], 'journals': []})
        self.assertEqual(self.client.get('/api/search?q= ').json(), {'tasks': [], 'journals': []})

    def test_source_journal_must_exist_and_match_analysis_text(self):
        self.assertEqual(self.client.post('/api/tasks', json={'title': 'Task', 'journal_id': 999}).status_code, 422)
        journal = self.client.post('/api/journals', json={'text': 'Saved'}).json()
        self.assertEqual(self.client.post('/api/ai/analyze', json={'text': 'Different', 'journal_id': journal['id']}).status_code, 422)
        self.assertEqual(self.client.post('/api/tasks', json={'title': 'Task', 'journal_id': True}).status_code, 422)

    def test_prioritization_endpoint_never_calls_the_model(self):
        self.assertIsNone(self.client.post('/api/ai/prioritize', json={}).json()['recommendation'])
        task = self.task(urgency_score=0, due_date='2026-11-12')
        result = self.client.post('/api/ai/prioritize', json={'reference_date': '2026-11-12'}).json()
        self.assertEqual(result['provider'], 'rules')
        self.assertEqual(result['recommendation']['task']['id'], task['id'])
        self.assertIn('Due today', result['recommendation']['explanation'])
        self.model.assert_not_called()


class SchedulingTests(unittest.TestCase):
    def test_explicit_and_relative_dates(self):
        reference = date(2026, 11, 12)
        for text, expected in [
            ('Submit on 2026-11-16.', '2026-11-16'), ('Finish today', '2026-11-12'),
            ('Read tomorrow', '2026-11-13'), ('Read day after tomorrow', '2026-11-14'),
            ('Submit Friday', '2026-11-13'), ('Submit next Friday', '2026-11-20'),
            ('내일 과제 제출', '2026-11-13'), ('다음 주 월요일 공부', '2026-11-16'),
            ('Sometime soon', None), ('Invalid 2026-02-30', None),
        ]:
            with self.subTest(text=text):
                self.assertEqual(due_date_from_text(text, reference), expected)

    def test_recommendation_ignores_completed_and_explains_deadlines(self):
        tasks = [
            {'id': 1, 'done': 0, 'urgency_score': 3, 'due_date': None},
            {'id': 2, 'done': 0, 'urgency_score': 0, 'due_date': '2026-11-11'},
            {'id': 3, 'done': 1, 'urgency_score': 3, 'due_date': '2026-11-10'},
        ]
        result = recommend(tasks, date(2026, 11, 12))
        self.assertEqual(result['task']['id'], 2)
        self.assertIn('Overdue', result['explanation'])
        self.assertIsNone(recommend([tasks[2]], date(2026, 11, 12)))

    def test_completion_uses_seoul_day_boundary(self):
        task = {'id': 1, 'done': 1, 'urgency_score': 1, 'due_date': None, 'completed_at': '2026-11-11T16:00:00+00:00'}
        self.assertEqual(dashboard([task], date(2026, 11, 12))['completed'], 1)


class ModelOutputTests(unittest.TestCase):
    def test_invalid_category_score_and_confidence_are_flagged(self):
        answers = {'answers': {'actionable': {'noul': 0.9}, 'category': {'choice': 'unknown', 'confidence': float('nan')}, 'urgency': {'score': 99, 'confidence': 1}}}
        with patch.dict('os.environ', {'TOGAS_AI_MODE': 'local'}), patch.object(ai, 'get_model') as get_model:
            get_model.return_value.decide.return_value = answers
            proposal = ai.analyze('Read notes.', date(2026, 11, 12))[0]
        self.assertEqual(proposal['category'], 'other')
        self.assertEqual(proposal['urgency_score'], 1)
        self.assertTrue(proposal['needs_review'])

    def test_non_finite_action_probability_fails_safely(self):
        with patch.dict('os.environ', {'TOGAS_AI_MODE': 'local'}), patch.object(ai, 'get_model') as get_model:
            get_model.return_value.decide.return_value = {'answers': {'actionable': {'noul': float('nan')}}}
            with self.assertRaises(ValueError):
                ai.analyze('Read notes.')


class MigrationTests(unittest.TestCase):
    def test_existing_starter_database_survives_repeated_startups(self):
        with TemporaryDirectory(prefix='togas-migration-', dir=Path(__file__).resolve().parents[2]) as directory:
            path = Path(directory) / 'old.db'
            with sqlite3.connect(path) as db:
                db.execute('CREATE TABLE tasks (id INTEGER PRIMARY KEY, title TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0, category TEXT NOT NULL DEFAULT "other", urgency_score REAL NOT NULL DEFAULT 1, created_at TEXT NOT NULL)')
                db.execute('INSERT INTO tasks VALUES (1, "Existing task", 0, "other", 1, "2026-11-01")')
            db.close()
            for _ in range(2):
                with patch.object(main, 'DB', path), TestClient(main.app) as client:
                    task = client.get('/api/tasks').json()[0]
                    self.assertEqual(task['title'], 'Existing task')
                    self.assertIsNone(task['due_date'])
                    self.assertIsNone(task['completed_at'])
