import sqlite3
from contextlib import contextmanager


_SOURCE_SCHEMA = (
    '''CREATE TABLE IF NOT EXISTS revisions (
        revision_id INTEGER PRIMARY KEY,
        roll_id TEXT NOT NULL,
        parent_revision_id INTEGER,
        UNIQUE (roll_id, revision_id),
        FOREIGN KEY (roll_id, parent_revision_id)
            REFERENCES revisions (roll_id, revision_id)
    )''',
    '''CREATE TABLE IF NOT EXISTS source_heads (
        roll_id TEXT PRIMARY KEY,
        revision_id INTEGER NOT NULL,
        FOREIGN KEY (roll_id, revision_id) REFERENCES revisions (roll_id, revision_id)
    )''',
    '''CREATE TABLE IF NOT EXISTS source_rows (
        revision_id INTEGER NOT NULL REFERENCES revisions (revision_id),
        position INTEGER NOT NULL CHECK (position > 0),
        row_no TEXT NOT NULL,
        delta TEXT NOT NULL,
        origin TEXT NOT NULL,
        PRIMARY KEY (revision_id, position),
        UNIQUE (revision_id, row_no)
    )''',
    '''CREATE TABLE IF NOT EXISTS frozen_revisions (
        frozen_id INTEGER PRIMARY KEY,
        roll_id TEXT NOT NULL,
        revision_id INTEGER NOT NULL,
        UNIQUE (roll_id, revision_id),
        FOREIGN KEY (roll_id, revision_id) REFERENCES revisions (roll_id, revision_id)
    )''',
)


def open_source_db(path):
    db = sqlite3.connect(path, isolation_level=None)
    db.execute('PRAGMA foreign_keys = ON')
    return db


@contextmanager
def source_transaction(db):
    db.execute('BEGIN IMMEDIATE')
    with db:
        yield


def initialize_source(db):
    with source_transaction(db):
        for statement in _SOURCE_SCHEMA:
            db.execute(statement)
