"""Task retries and Today/Jump Start/Focus integration, using isolated SQLite data."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
import ai
import main


class Day3TaskTests(unittest.TestCase):
    def setUp(self):
        self.resources = ExitStack()
        self.addCleanup(self.resources.close)
        directory = self.resources.enter_context(TemporaryDirectory(prefix='togas-day3-', dir=Path(__file__).resolve().parents[2]))
        self.path = Path(directory) / 'test.db'
        self.resources.enter_context(patch.object(main, 'DB', self.path))
        self.resources.enter_context(patch.dict('os.environ', {'TOGAS_AI_MODE': 'mock'}))
        self.model = self.resources.enter_context(patch.object(ai, 'JevDecision', side_effect=AssertionError('No live calls allowed')))
        self.client = self.resources.enter_context(TestClient(main.app))

    def create(self, **fields):
        response = self.client.post('/api/tasks', json={'title': 'Read notes', **fields})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_concurrent_retries_create_one_task(self):
        body = {'title': 'Read notes', 'request_id': str(uuid4()), 'urgency_score': 0}
        with ThreadPoolExecutor(max_workers=4) as pool:
            responses = list(pool.map(lambda _: self.client.post('/api/tasks', json=body), range(4)))
        self.assertTrue(all(response.status_code == 201 for response in responses))
        self.assertEqual(len({response.json()['id'] for response in responses}), 1)
        self.assertEqual(len(self.client.get('/api/tasks').json()), 1)
        self.assertNotIn('request_id', responses[0].json())

    def test_conflicting_token_leaves_original_unchanged(self):
        token = str(uuid4())
        task = self.create(request_id=token, urgency_score=0)
        for changes in [{'title': 'Different'}, {'urgency_score': 3}, {'due_date': '2026-11-15'}]:
            response = self.client.post('/api/tasks', json={'title': 'Read notes', 'urgency_score': 0, 'request_id': token, **changes})
            self.assertEqual(response.status_code, 409)
        self.assertEqual(self.client.get('/api/tasks').json(), [task])

    def test_equivalent_defaults_and_trimmed_titles_share_the_receipt(self):
        token = str(uuid4())
        task = self.create(request_id=token)
        retry = self.create(title='  Read notes  ', request_id=token, category='other', urgency_score=1.0, due_date=None, journal_id=None)
        self.assertEqual(retry, task)

    def test_retry_returns_current_record_without_undoing_edits_or_completion(self):
        body = {'title': 'Read notes', 'request_id': str(uuid4())}
        task = self.create(**body)
        updated = self.client.patch(f'/api/tasks/{task["id"]}', json={'title': 'Edited notes', 'done': True}).json()
        self.assertEqual(self.client.post('/api/tasks', json=body).json(), updated)
        self.assertEqual(self.client.get('/api/tasks').json(), [updated])

    def test_deleted_task_cannot_be_resurrected_by_delayed_retry(self):
        body = {'title': 'Read notes', 'request_id': str(uuid4())}
        task = self.create(**body)
        self.assertEqual(self.client.delete(f'/api/tasks/{task["id"]}').status_code, 204)
        self.assertEqual(self.client.post('/api/tasks', json=body).status_code, 409)
        self.assertEqual(self.client.get('/api/tasks').json(), [])
        self.create(request_id=str(uuid4()))

    def test_intentional_identical_tasks_and_legacy_clients_still_work(self):
        tasks = [self.create(), self.create(), self.create(request_id=str(uuid4())), self.create(request_id=str(uuid4()))]
        self.assertEqual(len({task['id'] for task in tasks}), 4)
        self.assertEqual(self.client.post('/api/tasks', json={'title': 'Read', 'request_id': 'invalid'}).status_code, 422)
        self.assertEqual(self.client.patch(f'/api/tasks/{tasks[0]["id"]}', json={'request_id': str(uuid4())}).status_code, 422)

    def test_invalid_source_does_not_consume_save_token(self):
        token = str(uuid4())
        response = self.client.post('/api/tasks', json={'title': 'Read', 'journal_id': 999, 'request_id': token})
        self.assertEqual(response.status_code, 422)
        task = self.create(title='Read', request_id=token)
        self.assertEqual(self.create(title='Read', request_id=token), task)

    def test_receipts_survive_restart_and_repeated_additive_migration(self):
        body = {'title': 'Read notes', 'request_id': str(uuid4())}
        task = self.create(**body)
        for _ in range(2):
            with TestClient(main.app) as client:
                self.assertEqual(client.post('/api/tasks', json=body).json(), task)
        with main.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM task_create_requests').fetchone()[0], 1)

    def test_full_recommendation_order_and_focus_completion(self):
        # Low urgency overdue work wins over high urgency future/undated work.
        cases = [
            ('overdue urgent older', '2026-11-13', 3),
            ('overdue urgent newer', '2026-11-13', 3),
            ('overdue lower urgency', '2026-11-12', 0),
            ('today', '2026-11-14', 0),
            ('tomorrow', '2026-11-15', 0),
            ('future earlier', '2026-11-17', 3),
            ('future later', '2026-11-18', 3),
            ('undated', None, 3),
        ]
        tasks = [self.create(title=title, due_date=due, urgency_score=urgency) for title, due, urgency in cases]
        for task in tasks:
            dashboard = self.client.get('/api/dashboard?today=2026-11-14').json()
            priority = self.client.post('/api/ai/prioritize', json={'reference_date': '2026-11-14'}).json()
            self.assertEqual(dashboard['recommendation']['task']['id'], task['id'])
            self.assertEqual(priority['recommendation'], dashboard['recommendation'])
            with patch.object(main, 'utcnow', return_value='2026-11-14T02:00:00+00:00'):
                completed = self.client.patch(f'/api/tasks/{task["id"]}', json={'done': True}).json()
            self.assertEqual(self.client.patch(f'/api/tasks/{task["id"]}', json={'done': True}).json()['completed_at'], completed['completed_at'])
        result = self.client.get('/api/dashboard?today=2026-11-14').json()
        self.assertEqual((result['completed'], result['total']), (8, 8))
        self.assertIsNone(result['recommendation'])
        self.assertEqual(self.client.get('/api/dashboard?today=2026-11-15').json()['total'], 0)
        reopened = self.client.patch(f'/api/tasks/{tasks[0]["id"]}', json={'done': False}).json()
        self.assertIsNone(reopened['completed_at'])
        self.assertEqual(self.client.get('/api/dashboard?today=2026-11-15').json()['recommendation']['task']['id'], reopened['id'])
        self.model.assert_not_called()
