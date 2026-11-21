from dataclasses import dataclass
from uuid import uuid4

from issue.body import WindowBody, encode_body
from issue.envelope import require_issuance_id, seal_envelope
from issue.evidence import build_sections
from issue.windows import normalize_windows, select_rows
from source.freeze import load_frozen
from source.store import source_transaction


@dataclass(frozen=True)
class IssuedPackage:
    issuance_id: str
    packet: bytes


def initialize_issues(db):
    with source_transaction(db):
        db.execute('''CREATE TABLE IF NOT EXISTS issued_packages (
            issuance_id TEXT PRIMARY KEY,
            frozen_id INTEGER NOT NULL REFERENCES frozen_revisions (frozen_id),
            packet BLOB NOT NULL
        )''')
        db.execute('CREATE INDEX IF NOT EXISTS issued_by_frozen ON issued_packages (frozen_id)')


def issue(db, frozen_id, windows):
    windows = normalize_windows(windows)
    revision = load_frozen(db, frozen_id).revision
    positions = select_rows(revision.rows, windows)
    sections = build_sections(revision.rows, positions)
    body = WindowBody(revision.roll_id, revision.revision_id, frozen_id, windows, sections)
    issuance_id = uuid4().hex
    packet = seal_envelope(issuance_id, encode_body(body))
    with source_transaction(db):
        db.execute(
            'INSERT INTO issued_packages (issuance_id, frozen_id, packet) VALUES (?, ?, ?)',
            (issuance_id, frozen_id, packet),
        )
    return IssuedPackage(issuance_id, packet)


def get_issued_package(db, issuance_id):
    require_issuance_id(issuance_id)
    row = db.execute(
        'SELECT packet FROM issued_packages WHERE issuance_id = ?', (issuance_id,)
    ).fetchone()
    if row is None:
        raise LookupError(f'unknown issuance {issuance_id}')
    return IssuedPackage(issuance_id, row[0])
