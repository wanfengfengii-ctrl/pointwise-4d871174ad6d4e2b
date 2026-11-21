from replay.limits import advance_reading
from replay.rationals import parse_rational
from replay.trace import Reading


def evaluate_window(body, initial):
    readings = []
    for section in body.sections:
        shift = parse_rational(section.evidence)
        current = advance_reading(initial, shift)
        for row in section.rows:
            current = advance_reading(current, row.delta)
            readings.append(Reading(row.row_no, current, row.origin))
    return tuple(readings)
