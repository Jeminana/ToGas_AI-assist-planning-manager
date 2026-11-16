"""Conservative action candidates. Pure rules; no model, storage or downloads.

Explicit intention grammar works with unseen verbs. A small imperative vocabulary
is only a fallback for demo detection and safe coordination boundaries, not NLP.
"""
from dataclasses import dataclass
import re


IMPERATIVES = (
    'finish', 'submit', 'study', 'read', 'write', 'buy', 'clean', 'call', 'send',
    'prepare', 'exercise', 'book', 'schedule', 'review', 'complete', 'pay', 'meet',
    'visit', 'attend', 'practice', 'renew', 'pick up', 'cook',
)
_INTENT = r'(?:I\s+)?(?:need\s+to|have\s+to|must|should|will|might|may|plan\s+to|want\s+to|intend\s+to|am\s+going\s+to|remember\s+to)\s+\w+'
_IMPERATIVE = r'(?:' + '|'.join(IMPERATIVES) + r')\b'
_PREFIX = r'(?:(?:today|tomorrow|tonight|on\s+\d{4}-\d{2}-\d{2})\s+)?(?:maybe\s+|perhaps\s+)?'
_COMMITMENT = r'I\s+(?:have|am\s+attending)\s+(?:a\s+|an\s+|the\s+)?(?:meeting|appointment|lecture)\b'
_HEAD = re.compile(r'^' + _PREFIX + r'(?:' + _INTENT + '|' + _IMPERATIVE + '|' + _COMMITMENT + r')', re.I)
_NEGATED = re.compile(
    r"\b(?:don't|do not|doesn't|does not|didn't|did not|won't|will not|"
    r"shouldn't|should not|mustn't|must not|can't|cannot|not going to|"
    r"no need|no longer need|not|never)\b|지\s*않|지\s*말|안\s*(?:할|해|하겠)|필요\s*없|않아도",
    re.I,
)
_COMPLETED = re.compile(
    r'\b(?:already|finished|completed)\b|'
    r'^(?:yesterday\s+)?I\s+(?:(?:have|had)\s+)?(?:met|cooked|bought|cleaned|submitted|sent|read\s+.+\s+yesterday)\b|'
    r'완료했|끝냈|제출했|공부했|청소했|운동했|만났|요리했|이미', re.I,
)
_ABBREVIATION = re.compile(r'\b(?:Mr|Mrs|Ms|Dr|Prof|Sr|Jr|vs|e\.g|i\.e|a\.m|p\.m)\.$|\b[A-Z]\.$', re.I)
_COORDINATION = re.compile(r',\s*(?:(?:and|then|but)\s+)?|\s+(?:and|then|but)\s+', re.I)
_AMBIGUOUS = 'Coordinated or ambiguous wording was kept together. Check whether it contains separate tasks.'
_VAGUE = re.compile(r'\b(?:be\s+(?:happier|happy|successful|better)|improve\s+my\s+life|do\s+better)\b', re.I)
_KOREAN_OBLIGATION = r'(?:해야|야\s*(?:해|한다)|(?:할|갈|볼|먹을)\s*예정)'
_KOREAN_BOUNDARY = re.compile(r'(?P<verb>제출|공부|청소|운동|요리|준비|전화)하고\s+')


@dataclass(frozen=True)
class Candidate:
    text: str
    source_text: str
    review_reasons: tuple[str, ...] = ()


def is_mock_action(text):
    """Recognize intentions, not arbitrary mentions of action words."""
    text = text.strip()
    if not text or _NEGATED.search(text) or _COMPLETED.search(text) or _VAGUE.search(text):
        return False
    if _HEAD.match(text):
        return True
    # Basic Korean obligations/plans and journal-style noun task endings.
    return bool(re.search(_KOREAN_OBLIGATION + r'|(?:공부|제출|청소|운동|예약|만나기)[.!。！]?$', text))


def _sentences(text):
    text = re.sub(r'(?m)^\s*(?:[-*•]|\d+[.)])\s+', '', text)
    for line in re.split(r'[;；]\s*|[\r\n]+', text):
        parts = []
        for part in re.split(r'(?<=[.!?。！？])\s+|(?<=[。！？])(?=\S)', line):
            if parts and _ABBREVIATION.search(parts[-1]):
                parts[-1] += ' ' + part
            else:
                parts.append(part)
        for part in parts:
            if part.strip(' -\t\r'):
                yield part.strip(' -\t\r')


def _unprotected_positions(text):
    """Do not treat coordination inside a quote or parentheses as a boundary."""
    positions, depth, quote = set(), 0, None
    for index, char in enumerate(text):
        if quote:
            if char == quote:
                quote = None
        elif char in '\"“':
            quote = '”' if char == '“' else char
        elif char == "'" and (index == 0 or not text[index - 1].isalnum()):
            quote = "'"
        elif char == '(':
            depth += 1
        elif char == ')':
            depth = max(0, depth - 1)
        elif not depth:
            positions.add(index)
    return positions


def candidates(text):
    result = []
    for source in _sentences(text):
        action_text = source
        reasons = []
        # Only remove a reflection prefix with an explicit causal intention.
        mixed = re.match(r"^(?:I\s+(?:am|feel)|I['’]m)\b.+?\bbecause\s+(?=I\s+(?:need|have|must|should|will|plan|want|intend)\b)", source, re.I)
        if mixed and not _NEGATED.search(source[:mixed.end()]):
            action_text = source[mixed.end():]
            reasons.append('An explicit intention was separated from a reflection; check the original sentence.')
        korean_mixed = re.match(r'^.+?(?:피곤|힘들|지쳤|우울|걱정|스트레스).+?(?:하지만|지만)\s*', source)
        if korean_mixed and re.search(_KOREAN_OBLIGATION, source[korean_mixed.end():]) and not _NEGATED.search(source[:korean_mixed.end()]):
            action_text = source[korean_mixed.end():]
            reasons.append('An explicit intention was separated from a reflection; check the original sentence.')
        parts = []
        start = 0
        safe = _unprotected_positions(action_text)
        for boundary in _COORDINATION.finditer(action_text):
            left = action_text[start:boundary.start()].strip()
            right = action_text[boundary.end():]
            # An explicit new subject can reset negation/completion scope;
            # a bare coordinated verb must inherit the original scope.
            left_head, right_head = _HEAD.match(left), _HEAD.match(right)
            left_complete = left_head and (left[left_head.end():].strip() or re.match(_INTENT, left, re.I) or re.search(_COMMITMENT, left, re.I))
            independent_right = re.match(r'^I\s+', right, re.I) and right_head
            safe_scope = (is_mock_action(left) and left_complete) or independent_right
            if boundary.start() in safe and safe_scope and right_head and right[right_head.end():].strip(' .!?'):
                parts.append(left)
                start = boundary.end()
        parts.append(action_text[start:].strip())
        if len(parts) == 1 and is_mock_action(action_text):
            korean_parts, korean_start = [], 0
            for boundary in _KOREAN_BOUNDARY.finditer(action_text):
                # Restrict to an action suffix followed by an independent
                # obligation. Object conjunctions such as 빵하고 stay intact.
                if boundary.start() in safe and re.search(_KOREAN_OBLIGATION, action_text[boundary.end():]):
                    korean_parts.append(action_text[korean_start:boundary.start()] + boundary['verb'])
                    korean_start = boundary.end()
            if korean_parts:
                parts = korean_parts + [action_text[korean_start:]]
        if len(parts) > 1:
            reasons.append('Multiple actions were separated from one sentence; check shared objects and deadlines in the original text.')
        for part in parts:
            part_reasons = list(reasons)
            if re.search(r'\band\b|,|하고|그리고', part, re.I):
                part_reasons.append(_AMBIGUOUS)
            if re.search(r'\b(?:maybe|perhaps|might|may)\b', part, re.I):
                part_reasons.append('This intention is tentative. Check whether you want to make it a task.')
            if len(parts) == 1 and len(re.findall(_IMPERATIVE, part, re.I)) > 1:
                part_reasons.append('Several action words lack a clear clause boundary. Add any missing task manually.')
            result.append(Candidate(part, source, tuple(part_reasons)))
    return result


def segment(text):
    """Compatibility helper used by API counts and evaluation tooling."""
    return [candidate.text for candidate in candidates(text)]
