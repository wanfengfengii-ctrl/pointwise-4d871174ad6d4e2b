from replay.limits import advance_reading
from replay.trace import Reading
from replay.transform import decode_transform


def evaluate_window(body, initial):
    current = initial
    readings = []
    for section in body.sections:
        current = decode_transform(section.evidence).apply(current)
        for row in section.rows:
            current = advance_reading(current, row.delta)
            readings.append(Reading(row.row_no, current, row.origin))
    return tuple(readings)
