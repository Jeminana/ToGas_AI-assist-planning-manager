"""Deterministic dates and recommendations. No model or network calls."""
from datetime import date, datetime, timedelta, timezone
import re

SEOUL = timezone(timedelta(hours=9))
WEEKDAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
KOREAN_WEEKDAYS = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']


def local_today():
    return datetime.now(SEOUL).date()


def due_date_from_text(text, reference):
    explicit = re.search(r'\b\d{4}-\d{2}-\d{2}\b', text)
    if explicit:
        try:
            return date.fromisoformat(explicit.group()).isoformat()
        except ValueError:
            return None
    lowered = text.casefold()
    for pattern, offset in [(r'\bday after tomorrow\b|모레', 2), (r'\btomorrow\b|내일', 1), (r'\btoday\b|오늘', 0)]:
        if re.search(pattern, lowered):
            return (reference + timedelta(days=offset)).isoformat()
    for index, (english, korean) in enumerate(zip(WEEKDAYS, KOREAN_WEEKDAYS)):
        match = re.search(r'\b(next\s+)?' + english + r'\b', lowered)
        if match or korean in lowered:
            offset = (7 - reference.weekday() + index) if ((match and match.group(1)) or re.search(r'다음\s*주', lowered)) else (index - reference.weekday()) % 7
            return (reference + timedelta(days=offset)).isoformat()
    return None


def rank_tasks(tasks, today):
    def rank(task):
        due = date.fromisoformat(task['due_date']) if task.get('due_date') else None
        bucket = (0 if due < today else 1 if due == today else 2 if (due - today).days == 1 else 3) if due else 3
        return bucket, -task['urgency_score'], -task.get('importance', 3), due or date.max, task['id']

    return sorted((task for task in tasks if not task['done']), key=rank)


def priority_explanation(task, today):

    due = task.get('due_date')
    reason = 'No deadline; eligible by urgency and importance.'
    if due:
        days = (date.fromisoformat(due) - today).days
        reason = 'Overdue tasks come first.' if days < 0 else 'Due today.' if days == 0 else 'Due tomorrow.' if days == 1 else f'Due on {due}.'
    return f'{reason} Urgency {task["urgency_score"]:g} of 3; importance {task.get("importance", 3)} of 5. Effort does not affect priority.'


def recommend(tasks, today):
    ranked = rank_tasks(tasks, today)
    return {'task': ranked[0], 'explanation': priority_explanation(ranked[0], today)} if ranked else None


def dashboard(tasks, today):
    def completed_today(task):
        stamp = task.get('completed_at')
        return bool(task['done'] and stamp and datetime.fromisoformat(stamp).astimezone(SEOUL).date() == today)

    current = [task for task in tasks if (not task['done'] and (not task.get('due_date') or task['due_date'] <= today.isoformat() or (task.get('scheduled_start') or '')[:10] == today.isoformat())) or completed_today(task)]
    scheduled = sorted((task for task in current if task.get('scheduled_start') and task['scheduled_start'][:10] == today.isoformat()), key=lambda task: (task['scheduled_start'], task['id']))
    return {'date': today.isoformat(), 'tasks': current, 'completed': sum(completed_today(task) for task in current), 'total': len(current), 'recommendation': recommend(tasks, today),
            'scheduled_tasks': scheduled, 'unscheduled_tasks': [task for task in current if not task.get('scheduled_start')],
            'overdue_tasks': [task for task in current if not task['done'] and task.get('due_date') and task['due_date'] < today.isoformat()]}
