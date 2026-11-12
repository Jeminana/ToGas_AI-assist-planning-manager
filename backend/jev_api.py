"""Official TypeSafe HTTP adapter. One POST, no retries or redirects.

Contract: https://docs.typesafe.ai/api/system-one
Credentials never enter a request body, result, log message, or exception text.
"""
from collections import OrderedDict
from copy import deepcopy
import hashlib
import json
import math
import os
import re
from threading import Lock
from time import monotonic
import httpx2 as httpx
import settings  # Loads .env locally; does not make requests.

JEV_ENDPOINT = 'https://api.typesafe.ai/v1/systemone'


class JevError(RuntimeError):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


class DecisionCache:
    def __init__(self, ttl=1800, capacity=32):
        self.ttl = ttl
        self.capacity = capacity
        self.entries = OrderedDict()
        # Also prevents simultaneous identical submissions from making two calls.
        self.lock = Lock()

    def get(self, key):
        entry = self.entries.get(key)
        if entry is None:
            return None
        timestamp, result = entry
        if monotonic() - timestamp >= self.ttl:
            del self.entries[key]
            return None
        self.entries.move_to_end(key)
        return deepcopy(result)

    def put(self, key, result):
        self.entries[key] = monotonic(), deepcopy(result)
        self.entries.move_to_end(key)
        while len(self.entries) > self.capacity:
            self.entries.popitem(last=False)


_CACHE = DecisionCache()


class JevDecision:
    def __init__(self, *, api_key=None, model=None, transport=None, cache=None):
        self._api_key = (api_key if api_key is not None else os.environ.get('JEV_API_KEY', '')).strip()
        self.model = model or os.environ.get('JEV_MODEL', 'jev-latest').strip()
        self.transport = transport
        self.cache = cache if cache is not None else _CACHE
        if not self._api_key:
            raise JevError('Jev API key is missing. Set JEV_API_KEY in your private .env file.')
        if not self.model:
            raise JevError('Jev model is missing. Set JEV_MODEL or use jev-latest.')

    def decide_many(self, sentences, questions, reference):
        if not sentences:
            return {'decisions': [], 'model': None, 'usage': None, 'request_count': 0, 'cached': False}
        if len(sentences) > 15:
            raise JevError('Split the entry into at most 15 segments per analysis.')
        state = {'reference_date': reference.isoformat(), 'segments': [
            {'id': f's{index}', 'text': text} for index, text in enumerate(sentences)
        ]}
        batched = {}
        for index in range(len(sentences)):
            for name, question in questions.items():
                batched[f's{index}_{name}'] = {
                    **question,
                    # Question ids are not shown to the model; target the segment
                    # explicitly in the instructions instead.
                    'instructions': f'Evaluate ONLY the text in segment s{index} of state.segments. Use reference_date for relative deadlines. {question["instructions"]}',
                }
        payload = {'model': self.model, 'state': state, 'questions': batched}
        fingerprint = hashlib.sha256(self._api_key.encode()).hexdigest()
        cache_key = hashlib.sha256((fingerprint + json.dumps(payload, sort_keys=True, ensure_ascii=False)).encode()).hexdigest()
        with self.cache.lock:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return {**cached, 'request_count': 0, 'cached': True}
            raw = self._post(payload)
            answers = raw.get('answers') if isinstance(raw, dict) else None
            if not isinstance(answers, dict):
                raise JevError('Jev returned an unexpected response. No suggestions were saved.')
            for key, question in batched.items():
                answer = answers.get(key)
                if not isinstance(answer, dict) or answer.get('type') != question['type']:
                    raise JevError('Jev returned a missing or incorrectly typed answer. No suggestions were saved.')
                if question['type'] == 'noul':
                    value = answer.get('noul')
                    try:
                        valid = not isinstance(value, bool) and math.isfinite(float(value)) and 0 <= float(value) <= 1
                    except (ValueError, TypeError):
                        valid = False
                    if not valid:
                        raise JevError('Jev returned an invalid actionability probability. No suggestions were saved.')
            returned_model = raw.get('model')
            if not isinstance(returned_model, str) or not re.fullmatch(r'[\w.-]{1,100}', returned_model) or self._api_key in returned_model:
                raise JevError('Jev returned an invalid model identifier.')
            usage = raw.get('usage')
            if isinstance(usage, dict):
                usage = {key: value for key, value in usage.items() if key in {'input_tokens', 'output_tokens'} and type(value) is int and value >= 0}
            else:
                usage = None
            result = {
                'decisions': [{'answers': {name: answers[f's{index}_{name}'] for name in questions}} for index in range(len(sentences))],
                'model': returned_model, 'usage': usage,
                'request_count': 1, 'cached': False,
            }
            # Only structurally complete HTTP successes are cached. The pipeline
            # still validates every decision value before proposing a task.
            self.cache.put(cache_key, result)
            return result

    def _post(self, payload):
        try:
            with httpx.Client(timeout=30.0, follow_redirects=False, transport=self.transport) as client:
                response = client.post(JEV_ENDPOINT, headers={
                    'Authorization': f'Bearer {self._api_key}', 'Content-Type': 'application/json',
                }, json=payload)
        except httpx.TimeoutException:
            raise JevError('Jev timed out. No automatic retry was made; try again later.') from None
        except httpx.RequestError:
            raise JevError('Could not connect to Jev. No automatic retry was made.') from None
        status = response.status_code
        if status != 200:
            hint = {
                401: 'The key was rejected; check the key or confirm the classroom service with your lecturer.',
                403: 'This key does not have access to the selected Jev model.',
                429: 'The shared service is rate limited; wait before trying again.',
                529: 'The service is overloaded; try again later.',
            }.get(status, 'The service could not complete this request; check the API configuration.')
            # Do not echo an upstream body, request, URL redirect, or headers.
            raise JevError(f'Jev request failed (HTTP {status}). {hint} No automatic retry was made.', status=status)
        try:
            return response.json()
        except ValueError:
            raise JevError('Jev returned invalid JSON. No automatic retry was made.') from None
