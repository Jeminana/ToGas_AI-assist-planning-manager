"""Single-day, deterministic placement. No writes, AI, or external services."""
from datetime import datetime, timedelta
from scheduling import rank_tasks, priority_explanation

PROVISIONAL_MINUTES = 30


def duration(task):
    return task.get('estimated_minutes') or task.get('scheduled_minutes') or PROVISIONAL_MINUTES


def reservation(task):
    start = datetime.fromisoformat(task['scheduled_start'])
    return start, start + timedelta(minutes=task.get('scheduled_minutes') or duration(task))


def overlaps(left, right):
    return left[0] < right[1] and right[0] < left[1]


def schedule_conflicts(tasks, reference, windows=None):
    confirmed = [task for task in tasks if task.get('scheduled_start') and task['scheduled_start'][:10] == reference.isoformat()]
    conflicts = []
    for index, task in enumerate(confirmed):
        start, end = reservation(task)
        if task.get('due_date') and (end - timedelta(microseconds=1)).date().isoformat() > task['due_date']:
            conflicts.append({'task_ids': [task['id']], 'code': 'deadline_conflict', 'reason': 'Confirmed time is after the deadline.'})
        if windows is not None and not any(start >= a and end <= b for a, b in windows):
            conflicts.append({'task_ids': [task['id']], 'code': 'outside_availability', 'reason': 'Confirmed time is outside saved availability.'})
        for other in confirmed[index + 1:]:
            if overlaps((start, end), reservation(other)):
                conflicts.append({'task_ids': [task['id'], other['id']], 'code': 'confirmed_overlap', 'reason': 'Confirmed tasks overlap. Their times were preserved.'})
    return conflicts


def time_windows(reference, windows):
    return sorted((datetime.fromisoformat(f'{reference.isoformat()}T{window["start"]}'), datetime.fromisoformat(f'{reference.isoformat()}T{window["end"]}')) for window in windows)


def propose_plan(tasks, reference, windows, max_tasks, existing_confirmed=None, context=None, not_before=None):
    """Greedy earliest-fit in priority order; do not move confirmed reservations.

    Optional user context is accepted for a future suitability policy. It does
    not change priority or placement in this version, and absence is supported.
    """
    available = time_windows(reference, windows)
    limited = not_before is not None and not_before.date() >= reference
    if limited:
        available = [(max(start, not_before), end) for start, end in available if end > not_before]
    confirmed = existing_confirmed if existing_confirmed is not None else [task for task in tasks if task.get('scheduled_start')]
    day_confirmed = [task for task in confirmed if task['scheduled_start'][:10] == reference.isoformat()]
    occupied = [reservation(task) for task in confirmed]
    confirmed_ids = {task['id'] for task in confirmed}
    placements, unscheduled = [], []
    for task in rank_tasks(tasks, reference):
        reason = None
        if task['id'] in confirmed_ids or task.get('scheduled_start'):
            reason = ('already_confirmed', 'Already has a confirmed time; it was preserved.')
        elif task.get('due_date') and task['due_date'] < reference.isoformat():
            reason = ('deadline_passed', 'The selected date is after this deadline. Change the deadline or schedule manually with the conflict visible.')
        elif len(day_confirmed) + len(placements) >= max_tasks:
            reason = ('daily_limit', 'The daily task limit is reached, including confirmed tasks.')
        else:
            minutes = task.get('estimated_minutes') or PROVISIONAL_MINUTES
            for window_start, window_end in available:
                start = window_start
                for busy_start, busy_end in sorted(occupied):
                    if busy_end <= start:
                        continue
                    if (busy_start - start).total_seconds() >= minutes * 60:
                        break
                    start = max(start, busy_end)
                if (window_end - start).total_seconds() >= minutes * 60:
                    end = start + timedelta(minutes=minutes)
                    placements.append({'task_id': task['id'], 'title': task['title'], 'start': start.isoformat(), 'end': end.isoformat(),
                                       'minutes': minutes, 'provisional': task.get('estimated_minutes') is None,
                                       'explanation': priority_explanation(task, reference)})
                    occupied.append((start, end))
                    break
            else:
                reason = ('no_remaining_window', 'No uninterrupted window in the remaining time fits this duration.') if limited else ('no_fitting_window', 'No uninterrupted available window fits this task duration.')
        if reason:
            unscheduled.append({'task_id': task['id'], 'title': task['title'], 'code': reason[0], 'reason': reason[1]})
    return {'date': reference.isoformat(), 'status': 'proposed', 'placements': placements, 'unscheduled': unscheduled,
            'confirmed': [{'task_id': task['id'], 'title': task['title'], 'start': task['scheduled_start'], 'minutes': task.get('scheduled_minutes') or duration(task),
                           'provisional': bool(task.get('scheduled_provisional'))} for task in sorted(day_confirmed, key=lambda item: (item['scheduled_start'], item['id']))],
            'conflicts': schedule_conflicts(confirmed, reference, time_windows(reference, windows)),
            'planning_from': not_before.isoformat() if limited else None,
            'context_note': 'User context is accepted but does not change placement or priority yet.' if context else None,
            'provisional_minutes': PROVISIONAL_MINUTES}


def validate_manual_schedule(task, tasks):
    """Keep a manual start fixed; reject duration edits that introduce overlap."""
    if not task.get('scheduled_start'):
        return
    start, end = reservation(task)
    if start.date() != (end - timedelta(microseconds=1)).date():
        raise ValueError('A scheduled task must fit within one local day.')
    for other in tasks:
        if other['id'] != task.get('id') and other.get('scheduled_start') and overlaps((start, end), reservation(other)):
            raise ValueError('This time or duration overlaps a confirmed task. Clear or change the starting time first.')
