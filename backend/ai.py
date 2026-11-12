"""Decision adapters and output normalization. No storage or automatic downloads."""
import importlib.util
import math
import os
from pathlib import Path
import re
from functools import lru_cache
import settings
from jev_api import JevDecision
from scheduling import due_date_from_text, local_today

MAX_SEGMENTS = 15

QUESTIONS = {
    "actionable": {
        "type": "noul",
        "instructions": "Does this text describe a specific action the writer needs or intends to do, rather than only a feeling, fact, or completed activity?",
    },
    "category": {
        "type": "choice",
        "instructions": "Which category best describes this task?",
        "criteria": {
            "study": "school, exam, homework, university, learning",
            "work": "job, project, internship, meeting, professional work",
            "personal": "household chores, errands, hobbies, personal administration",
            "health": "exercise, medical appointment, sleep, wellness",
            "other": "none of the above",
        },
    },
    "urgency": {
        "type": "score",
        "instructions": "How urgent is this action based only on the text and any explicitly mentioned deadline?",
        "criteria": ["not urgent", "low urgency", "moderately urgent", "highly urgent"],
    },
}

@lru_cache(maxsize=1)
def get_model():
    directory = os.environ.get('TOGAS_OPENJEVX_DIR')
    if not directory:
        raise RuntimeError('Set TOGAS_OPENJEVX_DIR to reviewed local model files')
    directory = Path(directory).resolve()
    names = ['openjevx.py', 'openjevx.w8.onnx', 'tokenizer.json', 'config.json']
    if not all((directory / name).is_file() for name in names):
        raise RuntimeError('Required local OpenJevX files are missing')
    module_path = directory / 'openjevx.py'
    spec = importlib.util.spec_from_file_location("openjevx", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.OpenJevX(model=str(directory / 'openjevx.w8.onnx'), tokenizer=str(directory / 'tokenizer.json'), config=str(directory / 'config.json'))


def ai_mode():
    return os.environ.get('TOGAS_AI_MODE', 'mock').strip().lower()

def segment(text: str) -> list[str]:
    """Conservative splitting, keeping common abbreviations and decimal text intact."""
    text = re.sub(r'(?m)^\s*(?:[-*•]|\d+[.)])\s+', '', text)
    sentences = []
    abbreviation = re.compile(r'\b(?:Mr|Mrs|Ms|Dr|Prof|Sr|Jr|vs|e\.g|i\.e|a\.m|p\.m)\.$|\b[A-Z]\.$', re.I)
    for line in re.split(r'[;；]\s*|[\r\n]+', text):
        parts = []
        for part in re.split(r'(?<=[.!?。！？])\s+|(?<=[。！？])(?=\S)', line):
            if parts and abbreviation.search(parts[-1]):
                parts[-1] += ' ' + part
            else:
                parts.append(part)
        for part in parts:
            sentences.extend(re.split(r'\band\s+(?=I\s+(?:need|have|must|should|will|plan|want|intend)\b)', part, flags=re.I))
    return [part.strip(' -\t\r') for part in sentences if part.strip(' -\t\r')]


class MockDecision:
    """Transparent rule-based stand-in for UI development, never a Jev evaluation."""
    def __init__(self, reference):
        self.reference = reference

    def decide(self, text, questions):
        action = bool(re.search(r'\b(need to|have to|must|should|plan to|will|remember to|finish|submit|study|read|write|buy|clean|call|send|prepare|exercise|book|schedule|review|complete|pay|meet|visit|attend|practice|renew|pick up)\b|해야|공부|제출|청소|운동|예약', text, re.I))
        if re.search(r"\b(already|yesterday|finished|completed|don't need|do not need|no need)\b|완료했|끝냈", text, re.I):
            action = False
        category = 'other'
        for name, pattern in {
            'study': r'exam|homework|assignment|nlp|study|lecture|notes|시험|과제|공부',
            'work': r'work|meeting|client|internship|report|업무|회의',
            'health': r'exercise|doctor|medical|walk|gym|운동|병원',
            'personal': r'clean|buy|grocer|room|pay|laundry|friend|청소|구매|친구',
        }.items():
            if re.search(pattern, text, re.I):
                category = name
                break
        due = due_date_from_text(text, self.reference)
        urgency = 3 if due and due <= self.reference.isoformat() else 2 if due else 1
        return {'answers': {
            'actionable': {'noul': 0.6 if action else 0.1},
            'category': {'choice': category, 'confidence': 0.5},
            'urgency': {'score': urgency, 'confidence': 0.5},
        }}


def number(value, lower, upper):
    if isinstance(value, bool):
        raise ValueError('Boolean decision value')
    result = float(value)
    if not math.isfinite(result) or not lower <= result <= upper:
        raise ValueError('Decision value outside expected range')
    return result


def confidence(value):
    try:
        return number(value, 0, 1)
    except (ValueError, TypeError):
        return 0.0

def analyze(text: str, reference=None) -> list[dict]:
    return analyze_result(text, reference)['proposals']


def analyze_result(text: str, reference=None) -> dict:
    reference = reference or local_today()
    mode = ai_mode()
    if mode == 'mock':
        model = MockDecision(reference)
    elif mode == 'local':
        model = get_model()
    elif mode == 'jev':
        model = JevDecision()
    else:
        raise RuntimeError('Analysis is disabled or the provider is not configured')
    proposals = []
    sentences = segment(text)[:MAX_SEGMENTS]
    metadata = {'model': None, 'usage': None, 'request_count': 0, 'cached': False}
    if mode == 'jev':
        batch = model.decide_many(sentences, QUESTIONS, reference)
        decisions = batch['decisions']
        metadata = {key: batch[key] for key in metadata}
    else:
        decisions = [model.decide(sentence, QUESTIONS) for sentence in sentences]
    for sentence, decision in zip(sentences, decisions):
        answers = decision['answers']
        action = answers["actionable"]
        probability = number(action["noul"], 0, 1)
        if probability < 0.5:
            continue
        cat = answers["category"]
        urg = answers["urgency"]
        cat_conf = confidence(cat.get('confidence'))
        urg_conf = confidence(urg.get('confidence'))
        reasons = []
        if mode == 'mock':
            reasons.append('This is a rule-based demo suggestion, not a Jev prediction.')
        if mode != 'mock' and probability < 0.8:
            reasons.append('It is uncertain whether this sentence describes an action.')
        category = cat.get('choice')
        if not isinstance(category, str) or category not in QUESTIONS['category']['criteria']:
            category, cat_conf = 'other', 0.0
            reasons.append('The category was unavailable; Other is a placeholder to check.')
        try:
            urgency = number(urg.get('score'), 0, 3)
        except (ValueError, TypeError):
            urgency, urg_conf = 1.0, 0.0
            reasons.append('The urgency was unavailable; Low is a placeholder to check.')
        if mode != 'mock' and cat_conf < 0.8:
            reasons.append('The suggested category is uncertain.')
        if mode != 'mock' and urg_conf < 0.8:
            reasons.append('The suggested urgency is uncertain.')
        if len(sentence) > 250:
            reasons.append('The task title was shortened; check it against the original text.')
        proposals.append({
            "title": sentence[:250],
            "source_text": sentence,
            "category": category,
            "urgency_score": round(urgency, 3),
            "due_date": due_date_from_text(sentence, reference),
            "action_probability": round(probability, 3),
            "category_confidence": round(cat_conf, 3),
            "urgency_confidence": round(urg_conf, 3),
            "needs_review": bool(reasons),
            "review_reasons": reasons,
            "title_truncated": len(sentence) > 250,
        })
    return {'proposals': proposals, 'provider': mode, **metadata}
