from source.revisions import append_revision
from source.sequence import validate_sequence, validate_text


def record(db, roll_id, rows, parent_revision_id=None):
    roll_id = validate_text(roll_id, 'roll ID')
    sequence = validate_sequence(rows)
    return append_revision(db, roll_id, sequence, parent_revision_id)
