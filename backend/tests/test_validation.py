"""HTTP validation checks using a temporary database; Jev is never invoked."""
from contextlib import ExitStack
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
import main


class InputValidationTests(unittest.TestCase):
    def setUp(self):
        self.resources = ExitStack()
        self.addCleanup(self.resources.close)
        directory = self.resources.enter_context(TemporaryDirectory(prefix='togas-validation-', dir=Path(__file__).resolve().parents[2]))
        self.resources.enter_context(patch.object(main, 'DB', Path(directory) / 'test.db'))
        # Safety guard: even a broken validation path must not call the model.
        self.analyze = self.resources.enter_context(patch.object(main, 'analyze', side_effect=AssertionError('Unexpected AI call')))
        self.client = self.resources.enter_context(TestClient(main.app))
        self.task = self.client.post('/api/tasks', json={'title': 'Original task'}).json()
        self.task_url = f'/api/tasks/{self.task["id"]}'

    def assert_rejected(self, response):
        self.assertEqual(response.status_code, 422, response.text)

    def test_blank_titles_rejected_on_create_and_update(self):
        for title in ['', ' ', '\t\r\n', '\u3000']:
            with self.subTest(title=repr(title)):
                self.assert_rejected(self.client.post('/api/tasks', json={'title': title}))
                self.assert_rejected(self.client.patch(self.task_url, json={'title': title}))
        self.assertEqual(self.client.get('/api/tasks').json(), [self.task])

    def test_title_limits_and_trimming_match_for_create_and_update(self):
        for title in ['a' * 251, '한' * 251]:
            self.assert_rejected(self.client.post('/api/tasks', json={'title': title}))
            self.assert_rejected(self.client.patch(self.task_url, json={'title': title}))
        boundary = '한' * 250
        response = self.client.post('/api/tasks', json={'title': f'  {boundary}\n'})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['title'], boundary)
        response = self.client.patch(self.task_url, json={'title': '  Updated title\t'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['title'], 'Updated title')

    def test_all_supported_categories_are_accepted(self):
        for category in ['study', 'work', 'personal', 'health', 'other']:
            with self.subTest(category=category):
                self.assertEqual(self.client.post('/api/tasks', json={'title': 'Task', 'category': category}).status_code, 201)
                self.assertEqual(self.client.patch(self.task_url, json={'category': category}).json()['category'], category)

    def test_unknown_categories_rejected_without_changing_stored_task(self):
        for category in ['', 'invalid', 'Study', 123, None]:
            with self.subTest(category=category):
                self.assert_rejected(self.client.post('/api/tasks', json={'title': 'Task', 'category': category}))
                self.assert_rejected(self.client.patch(self.task_url, json={'category': category}))
        self.assertEqual(self.client.get('/api/tasks').json(), [self.task])

    def test_urgency_bounds_and_numeric_types(self):
        for urgency in [-0.1, 3.1, 'NaN', 'Infinity', '-Infinity', '2', True, None]:
            with self.subTest(urgency=urgency):
                self.assert_rejected(self.client.post('/api/tasks', json={'title': 'Task', 'urgency_score': urgency}))
                self.assert_rejected(self.client.patch(self.task_url, json={'urgency_score': urgency}))
        for urgency in [0, 1.5, 3]:
            with self.subTest(urgency=urgency):
                response = self.client.post('/api/tasks', json={'title': 'Task', 'urgency_score': urgency})
                self.assertEqual(response.status_code, 201)
                self.assertEqual(response.json()['urgency_score'], urgency)
                self.assertEqual(self.client.patch(self.task_url, json={'urgency_score': urgency}).json()['urgency_score'], urgency)

    def test_invalid_journal_input_rejected_before_storage_or_ai(self):
        for text in ['', ' \r\n\t', '\u3000', 'a' * 10001, 42, None]:
            for endpoint in ['/api/journals', '/api/ai/analyze']:
                with self.subTest(endpoint=endpoint, length=len(text) if isinstance(text, str) else None):
                    self.assert_rejected(self.client.post(endpoint, json={'text': text}))
        self.analyze.assert_not_called()
        self.assertEqual(self.client.get('/api/journals').json(), [])

    def test_non_finite_urgency_returns_validation_error(self):
        for token in ['NaN', 'Infinity', '-Infinity']:
            with self.subTest(token=token):
                self.assert_rejected(self.client.post('/api/tasks', content='{"title":"Task","urgency_score":' + token + '}', headers={'Content-Type': 'application/json'}))
                self.assert_rejected(self.client.patch(self.task_url, content='{"urgency_score":' + token + '}', headers={'Content-Type': 'application/json'}))
        self.assertEqual(self.client.get('/api/tasks').json(), [self.task])

    def test_journal_length_boundary_and_original_formatting(self):
        for text in ['a' * 10000, '  First thought.\n\n- Second thought.\n']:
            response = self.client.post('/api/journals', json={'text': text})
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.json()['content'], text)
            self.assertEqual(self.client.get('/api/journals').json()[0]['content'], text)

    def test_missing_fields_and_unrecognized_fields_rejected(self):
        for endpoint in ['/api/tasks', '/api/journals', '/api/ai/analyze']:
            self.assert_rejected(self.client.post(endpoint, json={}))
        self.assert_rejected(self.client.post('/api/tasks', json={'title': 'Task', 'urgency': 3}))
        self.assert_rejected(self.client.patch(self.task_url, json={'title': 'New', 'unexpected': 'value'}))
        for endpoint in ['/api/journals', '/api/ai/analyze']:
            self.assert_rejected(self.client.post(endpoint, json={'text': 'Valid text', 'unexpected': True}))
        self.analyze.assert_not_called()
        self.assertEqual(self.client.get('/api/tasks').json(), [self.task])

    def test_patch_nulls_empty_body_and_strict_completion(self):
        self.assertEqual(self.client.patch(self.task_url, json={}).status_code, 400)
        for field in ['title', 'category', 'urgency_score', 'done']:
            self.assert_rejected(self.client.patch(self.task_url, json={field: None}))
        for done in ['false', 'true', 0, 1]:
            self.assert_rejected(self.client.patch(self.task_url, json={'done': done}))
        for done in [True, False]:
            response = self.client.patch(self.task_url, json={'done': done})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['done'], int(done))

    def test_rejected_patch_is_atomic(self):
        self.assert_rejected(self.client.patch(self.task_url, json={'title': 'Should not save', 'urgency_score': 9}))
        self.assertEqual(self.client.get('/api/tasks').json(), [self.task])

    def test_malformed_json_returns_readable_validation_error(self):
        response = self.client.post('/api/tasks', content='{"title":', headers={'Content-Type': 'application/json'})
        self.assert_rejected(response)
        error = response.json()['detail'][0]
        self.assertEqual(error['type'], 'json_invalid')
        self.assertTrue(error['msg'])
        self.assertNotIn('input', error)


if __name__ == '__main__':
    unittest.main()
