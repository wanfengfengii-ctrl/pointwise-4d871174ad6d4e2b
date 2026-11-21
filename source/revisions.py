from dataclasses import dataclass

from replay.rationals import encode_rational, parse_rational, require_database_id
from source.sequence import SourceRow, validate_text
from source.store import source_transaction


@dataclass(frozen=True)
class Revision:
    revision_id: int
    roll_id: str
    parent_revision_id: int | None
    rows: tuple[SourceRow, ...]


def append_revision(db, roll_id, rows, parent_revision_id=None):
    """Append a sequence already validated by intake and update its roll head."""
    if parent_revision_id is not None:
        require_database_id(parent_revision_id, 'parent revision ID')

    with source_transaction(db):
        if parent_revision_id is None:
            head = db.execute(
                'SELECT revision_id FROM source_heads WHERE roll_id = ?', (roll_id,)
            ).fetchone()
            parent_revision_id = head[0] if head else None
        else:
            parent = db.execute(
                'SELECT 1 FROM revisions WHERE roll_id = ? AND revision_id = ?',
                (roll_id, parent_revision_id),
            ).fetchone()
            if parent is None:
                raise ValueError('parent revision does not belong to the roll')

        revision_id = db.execute(
            'INSERT INTO revisions (roll_id, parent_revision_id) VALUES (?, ?)',
            (roll_id, parent_revision_id),
        ).lastrowid
        db.executemany(
            '''INSERT INTO source_rows (revision_id, position, row_no, delta, origin)
               VALUES (?, ?, ?, ?, ?)''',
            (
                (revision_id, position, str(row.row_no), encode_rational(row.delta), row.origin)
                for position, row in enumerate(rows, start=1)
            ),
        )
        db.execute(
            '''INSERT INTO source_heads (roll_id, revision_id) VALUES (?, ?)
               ON CONFLICT (roll_id) DO UPDATE SET revision_id = excluded.revision_id''',
            (roll_id, revision_id),
        )
    return revision_id


def load_revision(db, revision_id):
    require_database_id(revision_id, 'revision ID')
    head = db.execute(
        'SELECT roll_id, parent_revision_id FROM revisions WHERE revision_id = ?',
        (revision_id,),
    ).fetchone()
    if head is None:
        raise LookupError(f'unknown revision {revision_id}')
    rows = tuple(
        SourceRow(int(row_no), parse_rational(delta), origin)
        for row_no, delta, origin in db.execute(
            '''SELECT row_no, delta, origin FROM source_rows
               WHERE revision_id = ? ORDER BY position''',
            (revision_id,),
        )
    )
    return Revision(revision_id, head[0], head[1], rows)


def current_revision(db, roll_id):
    validate_text(roll_id, 'roll ID')
    head = db.execute(
        'SELECT revision_id FROM source_heads WHERE roll_id = ?', (roll_id,)
    ).fetchone()
    if head is None:
        raise LookupError(f'unknown roll {roll_id!r}')
    return load_revision(db, head[0])
