from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from ai import analyze_result as analyze, ai_mode, segment, MAX_SEGMENTS
from jev_api import JevError
from schemas import AnalysisInput, ISODate, JournalCreate, PriorityInput, TaskInput, TaskPatch
from scheduling import dashboard, local_today, recommend
from storage import connection, initialize, search_rows

DB = Path(__file__).with_name('togas.db')
DB_LOCK = Lock()


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
    return dashboard(tasks(), today or local_today())


@app.get('/api/tasks')
def tasks(q: str = ''):
    with connect() as db:
        return search_rows(db, 'tasks', 'title', q)


@app.post('/api/tasks', status_code=201)
def create_task(body: TaskInput):
    with DB_LOCK, connect() as db:
        if body.journal_id and not db.execute('SELECT 1 FROM journals WHERE id=?', (body.journal_id,)).fetchone():
            raise HTTPException(422, 'Source journal not found')
        cur = db.execute('INSERT INTO tasks(title, category, urgency_score, due_date, journal_id, created_at) VALUES (?,?,?,?,?,?)',
            (body.title, body.category, body.urgency_score, body.due_date.isoformat() if body.due_date else None, body.journal_id, utcnow()))
        return dict(db.execute('SELECT * FROM tasks WHERE id=?', (cur.lastrowid,)).fetchone())


@app.patch('/api/tasks/{task_id}')
def patch_task(task_id: int, body: TaskPatch):
    changes = body.model_dump(exclude_unset=True, mode='json')
    if not changes:
        raise HTTPException(400, 'No changes given')
    if any(value is None for key, value in changes.items() if key != 'due_date'):
        raise HTTPException(422, 'Null updates are only supported for clearing a deadline')
    with DB_LOCK, connect() as db:
        current = db.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone()
        if current is None:
            raise HTTPException(404, 'Task not found')
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
