"""Day 2.5 regressions: pure segmentation, offline extraction and mocked Jev."""
from contextlib import ExitStack
from datetime import date
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
import httpx2 as httpx
import ai
import main
from jev_api import DecisionCache, JevDecision
from segmentation import candidates, segment

REFERENCE = date(2026, 11, 14)


class SegmentationTests(unittest.TestCase):
    def test_multiple_actions_and_shared_objects(self):
        cases = [
            ('Meet friend. Cook for tonight.', ['Meet friend.', 'Cook for tonight.']),
            ('Buy milk and clean my room.', ['Buy milk', 'clean my room.']),
            ('Buy bread and butter.', ['Buy bread and butter.']),
            ('Study Python, cook dinner, and call my mother.', ['Study Python', 'cook dinner', 'call my mother.']),
            ('Buy bread, butter, and milk.', ['Buy bread, butter, and milk.']),
            ('Read notes and I intend to annotate them.', ['Read notes', 'I intend to annotate them.']),
            ('I need to study and i should clean my room.', ['I need to study', 'i should clean my room.']),
            ('Write "buy milk and clean my room" tomorrow.', ['Write "buy milk and clean my room" tomorrow.']),
            ('Read notes (and review examples) tomorrow.', ['Read notes (and review examples) tomorrow.']),
            ('Meet Dr. Kim tomorrow. Read chapter 3.5.', ['Meet Dr. Kim tomorrow.', 'Read chapter 3.5.']),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(segment(text), expected)

    def test_split_candidates_keep_the_original_sentence(self):
        text = 'Study Python, cook dinner, and call my mother.'
        result = candidates(text)
        self.assertEqual(len(result), 3)
        self.assertTrue(all(row.source_text == text for row in result))
        self.assertTrue(all(row.review_reasons for row in result))

    def test_ambiguous_coordination_and_korean_are_preserved_for_review(self):
        for text in ['Buy milk and polish the table.', 'Read and review my notes.', '내일 과제를 제출하고 친구를 만나야 해.']:
            with self.subTest(text=text):
                result = candidates(text)
                self.assertEqual([row.text for row in result], [text])
                self.assertEqual(result[0].source_text, text)
                self.assertTrue(any('kept together' in reason for reason in result[0].review_reasons))

    def test_empty_segments(self):
        for text in ['', ' \n\t', ';\n；', '- \n* ']:
            with self.subTest(text=text):
                self.assertEqual(segment(text), [])


class ExtractionTests(unittest.TestCase):
    def setUp(self):
        self.resources = ExitStack()
        self.addCleanup(self.resources.close)
        self.resources.enter_context(patch.dict('os.environ', {'TOGAS_AI_MODE': 'mock'}))
        self.live = self.resources.enter_context(patch.object(ai, 'JevDecision', side_effect=AssertionError('No live requests allowed')))
        self.local = self.resources.enter_context(patch.object(ai, 'get_model', side_effect=AssertionError('No local models allowed')))

    def test_original_two_task_example(self):
        result = ai.analyze_result('meet friend. cook for tonight.', REFERENCE)
        self.assertEqual([row['title'] for row in result['proposals']], ['meet friend.', 'cook for tonight.'])
        self.assertEqual(result['request_count'], 0)
        self.live.assert_not_called()
        self.local.assert_not_called()

    def test_requested_examples(self):
        cases = [
            ('Meet friend. Cook for tonight.', 2),
            ('Buy milk and clean my room.', 2),
            ('Buy bread and butter.', 1),
            ('Study Python, cook dinner, and call my mother.', 3),
            ('I feel tired today.', 0),
            ('I finished my assignment yesterday.', 0),
            ('I am stressed because I need to submit my report.', 1),
            ('내일 과제를 제출하고 친구를 만나야 해.', 1),  # documented conservative limitation
        ]
        for text, count in cases:
            with self.subTest(text=text):
                proposals = ai.analyze(text, REFERENCE)
                self.assertEqual(len(proposals), count)
                for proposal in proposals:
                    for field in ['title', 'source_text', 'category', 'urgency_score', 'due_date', 'review_reasons']:
                        self.assertIn(field, proposal)
                    self.assertTrue(proposal['needs_review'])

    def test_reflections_completed_and_negated_actions_do_not_create_tasks(self):
        texts = [
            'I feel tired and worried about the report.', 'I am stressed about cooking.',
            'My friend will cook dinner.', 'I already cleaned my room.',
            'I cooked dinner yesterday.', 'I have submitted my report.',
            'Do not buy anything today.', "Don't cook dinner.",
            "I don't need to meet my friend.", 'I will not buy milk and clean my room.',
            'I should not cook tonight.', 'I never buy bread.',
            'I need to not buy anything.', 'I intend not to cook tonight.',
            'I no longer need to submit the report.',
            'I feel I should not submit anything.', '오늘 기분이 좋다.',
            '오늘 과제를 제출했다.', '방 청소는 이미 끝냈다.',
            '과제를 제출하지 않아도 된다.',
        ]
        for text in texts:
            with self.subTest(text=text):
                self.assertEqual(ai.analyze(text, REFERENCE), [])

    def test_intention_grammar_supports_unlisted_verbs(self):
        for text in ['I intend to annotate the report.', 'I need to organize my desk.', 'Remember to water the plants.']:
            with self.subTest(text=text):
                self.assertEqual(len(ai.analyze(text, REFERENCE)), 1)

    def test_reflection_prefix_is_retained_as_source(self):
        text = 'I am stressed because I need to submit my report tomorrow.'
        proposal = ai.analyze(text, REFERENCE)[0]
        self.assertEqual(proposal['title'], 'I need to submit my report tomorrow.')
        self.assertEqual(proposal['source_text'], text)
        self.assertEqual(proposal['due_date'], '2026-11-15')
        self.assertTrue(any('reflection' in reason for reason in proposal['review_reasons']))

    def test_deadlines_are_not_silently_copied_between_split_actions(self):
        proposals = ai.analyze('Buy milk today and clean my room tomorrow.', REFERENCE)
        self.assertEqual([row['due_date'] for row in proposals], ['2026-11-14', '2026-11-15'])
        proposals = ai.analyze('Buy milk and clean my room tomorrow.', REFERENCE)
        self.assertEqual([row['due_date'] for row in proposals], [None, '2026-11-15'])
        self.assertTrue(all(any('deadlines' in reason for reason in row['review_reasons']) for row in proposals))

    def test_basic_korean_intentions(self):
        for text in ['내일 과제를 제출해야 한다.', '이번 주 금요일에 친구를 만나야 한다.', '내일 과제 제출.', '오늘 운동해야 한다.']:
            with self.subTest(text=text):
                self.assertEqual(len(ai.analyze(text, REFERENCE)), 1)


class PipelineIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.resources = ExitStack()
        self.addCleanup(self.resources.close)
        directory = self.resources.enter_context(TemporaryDirectory(prefix='togas-day25-', dir=Path(__file__).resolve().parents[2]))
        self.resources.enter_context(patch.object(main, 'DB', Path(directory) / 'test.db'))
        self.resources.enter_context(patch.dict('os.environ', {'TOGAS_AI_MODE': 'mock'}))
        self.client = self.resources.enter_context(TestClient(main.app))

    def test_saved_journal_and_existing_task_are_unchanged_until_explicit_approval(self):
        existing = self.client.post('/api/tasks', json={'title': 'Existing task'}).json()
        text = 'Buy milk and clean my room.'
        journal = self.client.post('/api/journals', json={'text': text}).json()
        with patch.object(ai, 'JevDecision', side_effect=AssertionError('No live calls')):
            result = self.client.post('/api/ai/analyze', json={'text': text, 'journal_id': journal['id']}).json()
        self.assertEqual(result['segments_processed'], 2)
        self.assertEqual(len(result['proposals']), 2)
        self.assertEqual(self.client.get('/api/tasks').json(), [existing])
        self.assertEqual(self.client.get('/api/journals').json(), [journal])
        proposal = result['proposals'][0]
        approved = self.client.post('/api/tasks', json={key: proposal[key] for key in ['title', 'category', 'urgency_score', 'due_date']}).json()
        self.assertEqual(len(self.client.get('/api/tasks').json()), 2)
        self.assertEqual(approved['title'], 'Buy milk')
        self.assertEqual(self.client.get('/api/journals').json(), [journal])

    def test_invalid_input_rejected_before_provider_or_storage(self):
        with patch.object(ai, 'JevDecision', side_effect=AssertionError('No live calls')):
            for body in [{}, {'text': ''}, {'text': '  '}, {'text': None}, {'text': 42}, {'text': 'x' * 10001}]:
                with self.subTest(body_type=type(body.get('text')).__name__):
                    self.assertEqual(self.client.post('/api/ai/analyze', json=body).status_code, 422)
        self.assertEqual(self.client.get('/api/journals').json(), [])
        self.assertEqual(self.client.get('/api/tasks').json(), [])

    def test_split_candidates_use_the_existing_jev_batch_contract(self):
        calls = []
        text = 'Buy milk and clean my room.'
        def handler(request):
            body = json.loads(request.content)
            calls.append(body)
            self.assertEqual(set(body), {'model', 'state', 'questions'})
            self.assertEqual([row['text'] for row in body['state']['segments']], ['Buy milk', 'clean my room.'])
            self.assertEqual(len(body['questions']), 6)
            answers = {}
            for key, question in body['questions'].items():
                kind = question['type']
                answers[key] = {'type': kind, **({'noul': 0.95} if kind == 'noul' else {'choice': 'personal', 'confidence': 0.95} if kind == 'choice' else {'score': 1, 'confidence': 0.95})}
            return httpx.Response(200, json={'model': 'jev-test-fixture', 'answers': answers})
        adapter = JevDecision(api_key='synthetic-only', transport=httpx.MockTransport(handler), cache=DecisionCache())
        with patch.dict('os.environ', {'TOGAS_AI_MODE': 'jev'}), patch.object(ai, 'JevDecision', return_value=adapter):
            response = self.client.post('/api/ai/analyze', json={'text': text, 'reference_date': REFERENCE.isoformat()})
        self.assertEqual(response.status_code, 200, response.text)
        proposals = response.json()['proposals']
        self.assertEqual(len(proposals), 2)
        self.assertTrue(all(row['source_text'] == text and row['needs_review'] for row in proposals))
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.client.get('/api/tasks').json(), [])
