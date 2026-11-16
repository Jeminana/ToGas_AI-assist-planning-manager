from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from threading import Lock
import json
import hashlib
import hmac
import secrets
from uuid import uuid4
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from ai import analyze_result as analyze, ai_mode, segment, MAX_SEGMENTS
from jev_api import JevError
from schemas import AnalysisInput, ISODate, JournalCreate, PriorityInput, TaskInput, TaskPatch, AvailabilityInput, PlanInput, PlanConfirmation
from scheduling import dashboard, local_today, recommend, SEOUL
from planning import propose_plan, validate_manual_schedule, schedule_conflicts, time_windows, PROVISIONAL_MINUTES
from storage import connection, initialize, search_rows

DB = Path(__file__).with_name('togas.db')
DB_LOCK = Lock()
PLAN_SECRET = secrets.token_bytes(32)


def connect():
    return connection(DB)


@asynccontextmanager
async def lifespan(app):
    with connect() as db:
        initialize(db)
    yield


app = FastAPI(title='ToGas API', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173'], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={
        'detail': [{'loc': error['loc'], 'msg': error['msg'], 'type': error['type']} for error in exc.errors()]
    })


def utcnow():
    return datetime.now(timezone.utc).isoformat()


@app.get('/api/health')
def health():
    return {'status': 'ok', 'ai_mode': ai_mode()}


@app.post('/api/ai/extract')
@app.post('/api/ai/analyze')
def ai_analyze(body: AnalysisInput):
    if body.journal_id:
        with connect() as db:
            journal = db.execute('SELECT * FROM journals WHERE id=?', (body.journal_id,)).fetchone()
        if not journal or journal['content'] != body.text:
            raise HTTPException(422, 'The saved journal must match the text being analyzed')
    try:
        result = analyze(body.text, body.reference_date or local_today())
    except JevError as exc:
        raise HTTPException(503, detail=f'{exc} Saved journals and tasks are unchanged.') from None
    except Exception as exc:
        raise HTTPException(503, detail=f'Analysis unavailable ({type(exc).__name__}). Saved journals and tasks are unchanged; try again or add tasks manually.') from exc
    count = len(segment(body.text))
    warnings = []
    if count > MAX_SEGMENTS:
        warnings.append(f'Only the first {MAX_SEGMENTS} of {count} segments were analyzed. Split the remaining text into another entry.')
    if ai_mode() == 'mock':
        warnings.append('Demo suggestions use rules, not Jev predictions. Review every suggestion.')
    return {**result, 'warnings': warnings, 'segments_processed': min(count, MAX_SEGMENTS), 'segments_total': count}


@app.post('/api/ai/prioritize')
def prioritize(body: PriorityInput):
    return {'recommendation': recommend(tasks(), body.reference_date or local_today()), 'provider': 'rules'}


@app.get('/api/dashboard')
def today_dashboard(today: ISODate | None = None):
    reference = today or local_today()
    with connect() as db:
        rows = search_rows(db, 'tasks', 'title')
        preference = read_preferences(db, reference)
    result = dashboard(rows, reference)
    result['schedule_conflicts'] = schedule_conflicts(rows, reference, time_windows(reference, preference['windows']) if preference['saved'] else None)
    return result


@app.get('/api/tasks')
def tasks(q: str = ''):
    with connect() as db:
        return search_rows(db, 'tasks', 'title', q)


@app.post('/api/tasks', status_code=201)
def create_task(body: TaskInput):
    with DB_LOCK, connect() as db:
        db.execute('BEGIN IMMEDIATE')
        token = str(body.request_id) if body.request_id else None
        fields = body.model_dump(mode='json', exclude={'request_id'})
        fields['urgency_score'] = float(body.urgency_score)
        payload = json.dumps(fields, sort_keys=True)
        if token:
            receipt = db.execute('SELECT task_id,payload FROM task_create_requests WHERE request_id=?', (token,)).fetchone()
            if receipt:
                # Receipts made before Day 3 omitted the new defaulted fields.
                old = TaskInput.model_validate(json.loads(receipt['payload'])).model_dump(mode='json', exclude={'request_id'})
                old['urgency_score'] = float(old['urgency_score'])
                if json.dumps(old, sort_keys=True) != payload:
                    raise HTTPException(409, 'This save request was already used for different task details.')
                saved = db.execute('SELECT * FROM tasks WHERE id=?', (receipt['task_id'],)).fetchone()
                if saved is None:
                    raise HTTPException(409, 'This task was already saved and later deleted. Reload your workspace before adding it again.')
                return dict(saved)
        if body.journal_id and not db.execute('SELECT 1 FROM journals WHERE id=?', (body.journal_id,)).fetchone():
            raise HTTPException(422, 'Source journal not found')
        values = {**fields, 'created_at': utcnow()}
        schedule_values(values)
        try:
            validate_manual_schedule(values, search_rows(db, 'tasks', 'title'))
        except (ValueError, OverflowError) as exc:
            raise HTTPException(409, str(exc)) from None
        columns = ','.join(values)
        cur = db.execute(f'INSERT INTO tasks({columns}) VALUES ({",".join("?" for _ in values)})', tuple(values.values()))
        if token:
            db.execute('INSERT INTO task_create_requests VALUES (?,?,?)', (token, cur.lastrowid, payload))
        return dict(db.execute('SELECT * FROM tasks WHERE id=?', (cur.lastrowid,)).fetchone())


@app.patch('/api/tasks/{task_id}')
def patch_task(task_id: int, body: TaskPatch):
    changes = body.model_dump(exclude_unset=True, mode='json')
    if not changes:
        raise HTTPException(400, 'No changes given')
    if any(value is None for key, value in changes.items() if key not in {'due_date', 'estimated_minutes', 'scheduled_start'}):
        raise HTTPException(422, 'Only deadline, duration and scheduled start may be cleared')
    with DB_LOCK, connect() as db:
        db.execute('BEGIN IMMEDIATE')
        current = db.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone()
        if current is None:
            raise HTTPException(404, 'Task not found')
        if any(key in changes and changes[key] != current[key] for key in ['scheduled_start', 'estimated_minutes']):
            candidate = {**dict(current), **changes}
            schedule_values(candidate)
            for key in ['scheduled_minutes', 'scheduled_provisional', 'schedule_status']:
                changes[key] = candidate[key]
            try:
                validate_manual_schedule(candidate, search_rows(db, 'tasks', 'title'))
            except (ValueError, OverflowError) as exc:
                raise HTTPException(409, str(exc)) from None
        if 'done' in changes:
            changes['done'] = int(changes['done'])
            changes['completed_at'] = (current['completed_at'] or utcnow()) if changes['done'] else None
        fields = ', '.join(f'{key}=?' for key in changes)
        db.execute(f'UPDATE tasks SET {fields} WHERE id=?', (*changes.values(), task_id))
        return dict(db.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone())


@app.delete('/api/tasks/{task_id}', status_code=204)
def delete_task(task_id: int):
    with DB_LOCK, connect() as db:
        if not db.execute('DELETE FROM tasks WHERE id=?', (task_id,)).rowcount:
            raise HTTPException(404, 'Task not found')


@app.get('/api/journals')
def journals(q: str = ''):
    with connect() as db:
        return search_rows(db, 'journals', 'content', q)


@app.post('/api/journals', status_code=201)
def save_journal(body: JournalCreate):
    with DB_LOCK, connect() as db:
        token = str(body.request_id) if body.request_id else None
        cur = db.execute('INSERT INTO journals(content,created_at,request_id) VALUES (?,?,?) ON CONFLICT(request_id) DO NOTHING', (body.text, utcnow(), token))
        row = db.execute('SELECT id,content,created_at FROM journals WHERE request_id=?' if token else 'SELECT id,content,created_at FROM journals WHERE id=?', (token or cur.lastrowid,)).fetchone()
        if row['content'] != body.text:
            raise HTTPException(409, 'This save request was already used for different journal text. Start a new entry.')
        return dict(row)


@app.get('/api/search')
def search(q: str = Query(default='', max_length=200)):
    if not q.strip():
        return {'tasks': [], 'journals': []}
    with connect() as db:
        return {'tasks': search_rows(db, 'tasks', 'title', q), 'journals': search_rows(db, 'journals', 'content', q)}


def schedule_values(values):
    confirmed = bool(values.get('scheduled_start'))
    values['schedule_status'] = 'confirmed' if confirmed else 'unscheduled'
    values['scheduled_minutes'] = (values.get('estimated_minutes') or PROVISIONAL_MINUTES) if confirmed else None
    values['scheduled_provisional'] = int(confirmed and values.get('estimated_minutes') is None)


def read_preferences(db, reference):
    row = db.execute('SELECT * FROM availability_preferences WHERE date=?', (reference.isoformat(),)).fetchone()
    return {'date': reference.isoformat(), 'windows': json.loads(row['windows']) if row else [], 'max_tasks': row['max_tasks'] if row else 5, 'saved': row is not None}


@app.get('/api/availability')
def availability(date: ISODate):
    with connect() as db:
        return read_preferences(db, date)


@app.put('/api/availability')
def save_availability(body: AvailabilityInput):
    with DB_LOCK, connect() as db:
        db.execute('INSERT INTO availability_preferences VALUES (?,?,?) ON CONFLICT(date) DO UPDATE SET windows=excluded.windows,max_tasks=excluded.max_tasks',
                   (body.date.isoformat(), json.dumps([window.model_dump() for window in body.windows]), body.max_tasks))
        return read_preferences(db, body.date)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def workspace_snapshot(rows, preference):
    return hashlib.sha256(canonical({'tasks': sorted(rows, key=lambda row: row['id']), 'availability': preference}).encode()).hexdigest()


def plan_signature(plan):
    return hmac.new(PLAN_SECRET, canonical(plan).encode(), hashlib.sha256).hexdigest()


@app.post('/api/planning/propose')
def generate_plan(body: PlanInput):
    with connect() as db:
        preference = read_preferences(db, body.date)
        rows = search_rows(db, 'tasks', 'title')
    if not preference['saved']:
        raise HTTPException(422, 'Save availability for this date before generating a plan.')
    if body.context and body.context.valid_for_date != body.date:
        raise HTTPException(422, 'Context must apply to the selected date.')
    cutoff = None
    if body.plan_from_now:
        current = datetime.fromisoformat(utcnow()).astimezone(SEOUL).replace(tzinfo=None)
        if current.date() == body.date:
            # Round upward so no proposed minute begins before the fixed clock.
            cutoff = current.replace(second=0, microsecond=0) + timedelta(minutes=bool(current.second or current.microsecond))
    plan = propose_plan(rows, body.date, preference['windows'], preference['max_tasks'], context=body.context, not_before=cutoff)
    plan.update(plan_id=str(uuid4()), snapshot=workspace_snapshot(rows, preference))
    return {**plan, 'signature': plan_signature(plan)}


@app.post('/api/planning/confirm')
def confirm_plan(body: PlanConfirmation):
    supplied = body.plan
    encoded = canonical(supplied)
    plan_id = supplied.get('plan_id')
    if not isinstance(plan_id, str):
        raise HTTPException(422, 'Missing plan id. Generate a new plan.')
    with DB_LOCK, connect() as db:
        db.execute('BEGIN IMMEDIATE')
        receipt = db.execute('SELECT * FROM schedule_confirmations WHERE plan_id=?', (plan_id,)).fetchone()
        if receipt:
            if receipt['payload'] != encoded:
                raise HTTPException(409, 'This plan id was already confirmed with different contents.')
            return json.loads(receipt['result'])
        unsigned = {key: value for key, value in supplied.items() if key != 'signature'}
        signature = supplied.get('signature')
        if not isinstance(signature, str) or not signature.isascii() or not hmac.compare_digest(signature, plan_signature(unsigned)):
            raise HTTPException(409, 'Plan expired or changed. Generate a fresh plan before confirming.')
        reference = datetime.fromisoformat(supplied['date']).date()
        rows = search_rows(db, 'tasks', 'title')
        preference = read_preferences(db, reference)
        if supplied['snapshot'] != workspace_snapshot(rows, preference):
            raise HTTPException(409, 'Tasks or availability changed. Generate a fresh plan before confirming.')
        if supplied.get('planning_from'):
            current = datetime.fromisoformat(utcnow()).astimezone(SEOUL).replace(tzinfo=None)
            if any(datetime.fromisoformat(placement['start']) < current for placement in supplied['placements']):
                raise HTTPException(409, 'A proposed start time has passed. Generate a fresh plan before confirming.')
        for placement in supplied['placements']:
            db.execute("UPDATE tasks SET scheduled_start=?,scheduled_minutes=?,scheduled_provisional=?,schedule_status='confirmed' WHERE id=?",
                       (placement['start'], placement['minutes'], int(placement['provisional']), placement['task_id']))
        result = {'status': 'confirmed', 'task_ids': [row['task_id'] for row in supplied['placements']]}
        db.execute('INSERT INTO schedule_confirmations VALUES (?,?,?)', (plan_id, encoded, canonical(result)))
        return result
