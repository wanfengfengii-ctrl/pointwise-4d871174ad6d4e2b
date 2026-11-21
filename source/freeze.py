from dataclasses import dataclass

from replay.rationals import require_database_id
from source.revisions import Revision, load_revision
from source.sequence import validate_text
from source.store import source_transaction


@dataclass(frozen=True)
class FrozenRevision:
    frozen_id: int
    revision: Revision


def freeze(db, roll_id, revision_id):
    validate_text(roll_id, 'roll ID')
    require_database_id(revision_id, 'revision ID')
    with source_transaction(db):
        revision = db.execute(
            'SELECT 1 FROM revisions WHERE roll_id = ? AND revision_id = ?',
            (roll_id, revision_id),
        ).fetchone()
        if revision is None:
            raise LookupError('unknown revision for the supplied roll')
        db.execute(
            '''INSERT INTO frozen_revisions (roll_id, revision_id) VALUES (?, ?)
               ON CONFLICT (roll_id, revision_id) DO NOTHING''',
            (roll_id, revision_id),
        )
        frozen_id, = db.execute(
            'SELECT frozen_id FROM frozen_revisions WHERE roll_id = ? AND revision_id = ?',
            (roll_id, revision_id),
        ).fetchone()
    return frozen_id


def load_frozen(db, frozen_id):
    require_database_id(frozen_id, 'frozen ID')
    row = db.execute(
        'SELECT revision_id FROM frozen_revisions WHERE frozen_id = ?', (frozen_id,)
    ).fetchone()
    if row is None:
        raise LookupError(f'unknown frozen revision {frozen_id}')
    return FrozenRevision(frozen_id, load_revision(db, row[0]))
