from replay.limits import advance_reading
from replay.trace import Reading, ReplayTrace
from replay.validate import validate_initial_value
from source.freeze import load_frozen


def replay(db, frozen_id, initial_value):
    initial = validate_initial_value(initial_value)
    revision = load_frozen(db, frozen_id).revision
    current = initial
    readings = []
    for row in revision.rows:
        current = advance_reading(current, row.delta)
        readings.append(Reading(row.row_no, current, row.origin))
    return ReplayTrace(
        revision.roll_id, revision.revision_id, frozen_id, initial, tuple(readings)
    )
