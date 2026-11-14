"""Day 3 placement/confirmation regressions. Temporary data and no live AI."""
from concurrent.futures import ThreadPoolExecutor
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
import ai
import main
from planning import propose_plan
from scheduling import rank_tasks
from storage import connection

DAY = date(2026, 11, 14)
WINDOWS = [{'start': '09:00', 'end': '10:00'}, {'start': '13:00', 'end': '14:00'}]


def task(task_id, **fields):
    return {'id': task_id, 'title': f'Task {task_id}', 'done': 0, 'urgency_score': 1, 'importance': 3, 'effort_level': 3, 'due_date': None, 'estimated_minutes': 30, **fields}


class PriorityPlacementTests(unittest.TestCase):
    def test_priority_buckets_importance_and_deterministic_ties(self):
        rows = [task(8), task(7, due_date='2026-11-18'), task(6, importance=5),
                task(5, urgency_score=3), task(4, due_date='2026-11-15', urgency_score=0),
                task(3, due_date='2026-11-14', urgency_score=0), task(2, due_date='2026-11-13'),
                task(1, due_date='2026-11-13', effort_level=5), task(0, done=1)]
        self.assertEqual([row['id'] for row in rank_tasks(rows, DAY)], [1, 2, 3, 4, 5, 6, 7, 8])
        self.assertEqual(rank_tasks(rows, DAY), rank_tasks(list(reversed(rows)), DAY))

    def test_multiple_windows_unknown_duration_and_too_long(self):
        rows = [task(1, estimated_minutes=60), task(2, estimated_minutes=None), task(3, estimated_minutes=90)]
        result = propose_plan(rows, DAY, WINDOWS, 5)
        self.assertEqual([row['start'] for row in result['placements']], ['2026-11-14T09:00:00', '2026-11-14T13:00:00'])
        self.assertTrue(result['placements'][1]['provisional'])
        self.assertEqual(result['placements'][1]['minutes'], 30)
        self.assertEqual(result['unscheduled'][0]['code'], 'no_fitting_window')
        self.assertIsNone(rows[1]['estimated_minutes'])

    def test_confirmed_times_remain_fixed_and_reserve_capacity(self):
        rows = [task(1, scheduled_start='2026-11-14T09:15:00', scheduled_minutes=30), task(2, estimated_minutes=20)]
        result = propose_plan(rows, DAY, WINDOWS, 2)
        self.assertEqual(result['placements'][0]['start'], '2026-11-14T13:00:00')
        self.assertEqual(result['confirmed'][0]['start'], '2026-11-14T09:15:00')
        limited = propose_plan(rows, DAY, WINDOWS, 1)
        self.assertEqual(limited['placements'], [])
        self.assertEqual(limited['unscheduled'][1]['code'], 'daily_limit')

    def test_existing_overlaps_are_flagged_and_not_rearranged(self):
        confirmed = [task(1, scheduled_start='2026-11-14T09:00:00', scheduled_minutes=40), task(2, scheduled_start='2026-11-14T09:20:00', scheduled_minutes=40)]
        result = propose_plan([task(3)], DAY, WINDOWS, 5, existing_confirmed=confirmed)
        self.assertEqual(result['placements'][0]['start'], '2026-11-14T13:00:00')
        self.assertIn('confirmed_overlap', [row['code'] for row in result['conflicts']])

    def test_deadlines_context_and_absence_of_context(self):
        rows = [task(1, due_date='2026-11-13'), task(2, due_date='2026-11-14'), task(3, estimated_minutes=None)]
        plain = propose_plan(rows, DAY, WINDOWS, 5)
        contextual = propose_plan(rows, DAY, WINDOWS, 5, context={'energy_level': 'low', 'source': 'user', 'valid_for_date': DAY.isoformat()})
        self.assertEqual(plain['placements'], contextual['placements'])
        self.assertEqual(plain['unscheduled'][0]['code'], 'deadline_passed')
        self.assertTrue(all(row['explanation'] for row in plain['placements']))
        self.assertIsNotNone(contextual['context_note'])

    def test_completed_tasks_are_not_placed_but_confirmed_history_stays_reserved(self):
        result = propose_plan([task(1, done=1, scheduled_start='2026-11-14T09:00:00', scheduled_minutes=60), task(2)], DAY, WINDOWS, 3)
        self.assertEqual([row['task_id'] for row in result['placements']], [2])
        self.assertEqual(result['placements'][0]['start'], '2026-11-14T13:00:00')

    def test_unfittable_high_priority_task_does_not_block_shorter_work(self):
        rows = [task(1, urgency_score=3, estimated_minutes=90), task(2, estimated_minutes=30)]
        result = propose_plan(rows, DAY, list(reversed(WINDOWS)), 5)
        self.assertEqual(result['unscheduled'][0]['task_id'], 1)
        self.assertEqual(result['placements'][0]['task_id'], 2)
        self.assertEqual(result['placements'][0]['start'], '2026-11-14T09:00:00')


class PlanningApiTests(unittest.TestCase):
    def setUp(self):
        self.resources = ExitStack()
        self.addCleanup(self.resources.close)
        directory = self.resources.enter_context(TemporaryDirectory(prefix='togas-planning-', dir=Path(__file__).resolve().parents[2]))
        self.path = Path(directory) / 'test.db'
        self.resources.enter_context(patch.object(main, 'DB', self.path))
        self.resources.enter_context(patch.dict('os.environ', {'TOGAS_AI_MODE': 'mock'}))
        self.resources.enter_context(patch.object(ai, 'JevDecision', side_effect=AssertionError('No live calls')))
        self.client = self.resources.enter_context(TestClient(main.app))

    def create(self, **fields):
        response = self.client.post('/api/tasks', json={'title': 'Plan task', **fields})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def preferences(self, **fields):
        response = self.client.put('/api/availability', json={'date': DAY.isoformat(), 'windows': WINDOWS, 'max_tasks': 5, **fields})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def plan(self):
        response = self.client.post('/api/planning/propose', json={'date': DAY.isoformat()})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def confirm(self, plan):
        return self.client.post('/api/planning/confirm', json={'plan': plan})

    def test_metadata_defaults_validation_and_clearing_duration(self):
        row = self.create()
        self.assertEqual((row['importance'], row['effort_level'], row['estimated_minutes'], row['schedule_status']), (3, 3, None, 'unscheduled'))
        url = f'/api/tasks/{row["id"]}'
        for field, values in {'importance': [0, 6, True, 2.5, '3', None], 'effort_level': [0, 6, False], 'estimated_minutes': [0, -1, 1441, True, '30', 1.5], 'scheduled_start': ['2026-11-14', 0, 'not a date']}.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    self.assertEqual(self.client.patch(url, json={field: value}).status_code, 422)
        updated = self.client.patch(url, json={'importance': 5, 'effort_level': 1, 'estimated_minutes': 40}).json()
        self.assertEqual((updated['importance'], updated['estimated_minutes']), (5, 40))
        self.assertIsNone(self.client.patch(url, json={'estimated_minutes': None}).json()['estimated_minutes'])

    def test_availability_validation_and_persistence(self):
        saved = self.preferences()
        with TestClient(main.app) as client:
            self.assertEqual(client.get('/api/availability', params={'date': DAY.isoformat()}).json(), saved)
        for changes in [{'windows': []}, {'windows': [{'start': '10:00', 'end': '09:00'}]}, {'windows': [{'start': '9:00', 'end': '10:00'}]}, {'windows': [WINDOWS[0], WINDOWS[0]]}, {'max_tasks': 0}, {'max_tasks': True}, {'date': 'invalid'}]:
            response = self.client.put('/api/availability', json={'date': DAY.isoformat(), 'windows': WINDOWS, 'max_tasks': 5, **changes})
            self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.client.get('/api/availability', params={'date': DAY.isoformat()}).json(), saved)

    def test_proposals_and_rejection_do_not_persist_task_times(self):
        row = self.create()
        self.assertEqual(self.client.post('/api/planning/propose', json={'date': DAY.isoformat()}).status_code, 422)
        self.preferences()
        plan = self.plan()
        self.assertEqual(plan['status'], 'proposed')
        self.assertTrue(plan['placements'][0]['provisional'])
        # Rejecting/discarding this response requires no database mutation.
        self.assertEqual(self.client.get('/api/tasks').json(), [row])
        with main.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM schedule_confirmations').fetchone()[0], 0)

    def test_confirmation_is_atomic_retry_safe_and_preserves_unknown_estimate(self):
        self.create()
        self.preferences()
        plan = self.plan()
        with ThreadPoolExecutor(max_workers=4) as pool:
            responses = list(pool.map(lambda _: self.confirm(plan), range(4)))
        self.assertTrue(all(response.status_code == 200 for response in responses))
        self.assertTrue(all(response.json() == responses[0].json() for response in responses))
        row = self.client.get('/api/tasks').json()[0]
        self.assertEqual((row['schedule_status'], row['scheduled_minutes'], row['scheduled_provisional']), ('confirmed', 30, 1))
        self.assertIsNone(row['estimated_minutes'])
        with main.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM schedule_confirmations').fetchone()[0], 1)

    def test_confirmation_replay_survives_restart_and_never_undoes_completion(self):
        row = self.create(estimated_minutes=20)
        self.preferences()
        plan = self.plan()
        self.assertEqual(self.confirm(plan).status_code, 200)
        completed = self.client.patch(f'/api/tasks/{row["id"]}', json={'done': True}).json()
        with patch.object(main, 'PLAN_SECRET', b'new-process-secret'), TestClient(main.app) as client:
            self.assertEqual(client.post('/api/planning/confirm', json={'plan': plan}).status_code, 200)
            self.assertEqual(client.get('/api/tasks').json(), [completed])
        self.assertEqual(self.plan()['placements'], [])

    def test_stale_plans_rejected_after_task_edit_completion_deletion_or_preference_change(self):
        row = self.create()
        self.preferences()
        for change in [{'title': 'Edited task'}, {'done': True}]:
            plan = self.plan()
            self.client.patch(f'/api/tasks/{row["id"]}', json=change)
            self.assertEqual(self.confirm(plan).status_code, 409)
        plan = self.plan()
        self.preferences(max_tasks=2)
        self.assertEqual(self.confirm(plan).status_code, 409)
        plan = self.plan()
        self.client.delete(f'/api/tasks/{row["id"]}')
        self.assertEqual(self.confirm(plan).status_code, 409)

    def test_changed_or_expired_proposal_cannot_be_confirmed(self):
        self.create(); self.preferences()
        plan = self.plan()
        plan['placements'][0]['start'] = '2026-11-14T22:00:00'
        self.assertEqual(self.confirm(plan).status_code, 409)
        plan = self.plan()
        with patch.object(main, 'PLAN_SECRET', b'new-process-secret'):
            self.assertEqual(self.confirm(plan).status_code, 409)
        self.assertIsNone(self.client.get('/api/tasks').json()[0]['scheduled_start'])

    def test_manual_times_and_duration_edits_never_overlap_confirmed_tasks(self):
        first = self.create(scheduled_start='2026-11-14T09:00', estimated_minutes=30)
        second = self.create(title='Second', scheduled_start='2026-11-14T09:30', estimated_minutes=30)
        self.assertEqual(self.client.patch(f'/api/tasks/{first["id"]}', json={'estimated_minutes': 45}).status_code, 409)
        self.assertEqual(self.client.post('/api/tasks', json={'title': 'Overlapping', 'scheduled_start': '2026-11-14T09:15'}).status_code, 409)
        self.assertEqual(self.client.patch(f'/api/tasks/{second["id"]}', json={'scheduled_start': '2026-11-14T09:15'}).status_code, 409)
        edited = self.client.patch(f'/api/tasks/{first["id"]}', json={'title': 'New title', 'importance': 5}).json()
        self.assertEqual(edited['scheduled_start'], first['scheduled_start'])
        cleared = self.client.patch(f'/api/tasks/{second["id"]}', json={'scheduled_start': None}).json()
        self.assertEqual((cleared['schedule_status'], cleared['scheduled_minutes']), ('unscheduled', None))
        self.assertEqual(self.client.patch(f'/api/tasks/{first["id"]}', json={'estimated_minutes': 45}).status_code, 200)

    def test_local_datetime_normalization_and_deadline_conflict_display(self):
        row = self.create(scheduled_start='2026-11-14T00:00:00Z', estimated_minutes=30, due_date='2026-11-13')
        self.assertEqual(row['scheduled_start'], '2026-11-14T09:00:00')
        dashboard = self.client.get('/api/dashboard?today=2026-11-14').json()
        self.assertEqual(dashboard['scheduled_tasks'][0]['id'], row['id'])
        self.assertEqual(dashboard['schedule_conflicts'][0]['code'], 'deadline_conflict')
        self.assertEqual(dashboard['overdue_tasks'][0]['id'], row['id'])

    def test_today_includes_future_deadline_scheduled_tasks_in_chronological_order(self):
        later = self.create(scheduled_start='2026-11-14T13:00', due_date='2026-11-20')
        earlier = self.create(scheduled_start='2026-11-14T09:00', due_date='2026-11-20')
        result = self.client.get('/api/dashboard?today=2026-11-14').json()
        self.assertEqual([row['id'] for row in result['scheduled_tasks']], [earlier['id'], later['id']])
        self.assertEqual(result['total'], 2)
        self.assertEqual(result['unscheduled_tasks'], [])

    def test_context_is_optional_validated_and_explicitly_not_a_priority_factor(self):
        self.create(); self.preferences()
        plan = self.plan()
        context = {'energy_level': 'low', 'source': 'user', 'valid_for_date': DAY.isoformat()}
        response = self.client.post('/api/planning/propose', json={'date': DAY.isoformat(), 'context': context})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['placements'], plan['placements'])
        self.assertTrue(response.json()['context_note'])
        context['valid_for_date'] = '2026-11-15'
        self.assertEqual(self.client.post('/api/planning/propose', json={'date': DAY.isoformat(), 'context': context}).status_code, 422)

    def test_legacy_database_migrates_without_losing_tasks_journals_or_receipts(self):
        path = self.path.with_name('legacy.db')
        token = str(uuid4())
        with connection(path) as db:
            db.execute('CREATE TABLE tasks (id INTEGER PRIMARY KEY, title TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0, category TEXT NOT NULL DEFAULT "other", urgency_score REAL NOT NULL DEFAULT 1, created_at TEXT NOT NULL)')
            db.execute('INSERT INTO tasks VALUES (1,"Legacy task",0,"other",1,"2026-11-12")')
            db.execute('CREATE TABLE journals (id INTEGER PRIMARY KEY, content TEXT NOT NULL, created_at TEXT NOT NULL)')
            db.execute('INSERT INTO journals VALUES (1,"Legacy journal","2026-11-12")')
            db.execute('CREATE TABLE task_create_requests (request_id TEXT PRIMARY KEY, task_id INTEGER NOT NULL, payload TEXT NOT NULL)')
            db.execute('INSERT INTO task_create_requests VALUES (?,?,?)', (token, 1, json.dumps({'title': 'Legacy task', 'category': 'other', 'urgency_score': 1.0, 'due_date': None, 'journal_id': None})))
        for _ in range(2):
            with patch.object(main, 'DB', path), TestClient(main.app) as client:
                row = client.get('/api/tasks').json()[0]
                self.assertEqual((row['title'], row['importance'], row['estimated_minutes'], row['effort_level']), ('Legacy task', 3, None, 3))
                self.assertEqual(client.get('/api/journals').json()[0]['content'], 'Legacy journal')
                self.assertEqual(client.post('/api/tasks', json={'title': 'Legacy task', 'request_id': token}).json()['id'], 1)
                self.assertEqual(len(client.get('/api/tasks').json()), 1)
