"""SQLite connection lifetime and additive schema upgrades."""
from contextlib import contextmanager
import sqlite3


@contextmanager
def connection(path):
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.create_function('casefold', 1, lambda value: (value or '').casefold(), deterministic=True)
    try:
        with db:
            yield db
    finally:
        db.close()


def initialize(db):
    db.execute('CREATE TABLE IF NOT EXISTS journals (id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT NOT NULL, created_at TEXT NOT NULL)')
    journal_columns = {row['name'] for row in db.execute('PRAGMA table_info(journals)')}
    if 'request_id' not in journal_columns:
        db.execute('ALTER TABLE journals ADD COLUMN request_id TEXT')
    db.execute('CREATE UNIQUE INDEX IF NOT EXISTS journals_request_id ON journals(request_id)')
    db.execute('CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0, category TEXT NOT NULL DEFAULT "other", urgency_score REAL NOT NULL DEFAULT 1.0, created_at TEXT NOT NULL)')
    columns = {row['name'] for row in db.execute('PRAGMA table_info(tasks)')}
    for name, declaration in {'due_date': 'TEXT', 'completed_at': 'TEXT', 'journal_id': 'INTEGER REFERENCES journals(id)'}.items():
        if name not in columns:
            db.execute(f'ALTER TABLE tasks ADD COLUMN {name} {declaration}')


def search_rows(db, table, column, query=''):
    if (table, column) not in {('tasks', 'title'), ('journals', 'content')}:
        raise ValueError('Unsupported search target')
    ordering = 'done ASC, urgency_score DESC, id DESC' if table == 'tasks' else 'id DESC'
    columns = '*' if table == 'tasks' else 'id, content, created_at'
    return [dict(row) for row in db.execute(
        f'SELECT {columns} FROM {table} WHERE instr(casefold({column}), ?) > 0 ORDER BY {ordering}',
        (query.strip().casefold(),),
    )]
