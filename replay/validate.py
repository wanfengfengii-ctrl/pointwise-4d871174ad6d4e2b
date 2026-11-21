from replay.limits import LOWER_LIMIT, UPPER_LIMIT
from replay.rationals import parse_rational


def validate_initial_value(value):
    initial = parse_rational(value)
    if not LOWER_LIMIT <= initial <= UPPER_LIMIT:
        raise ValueError('initial reading must lie in [0, 10]')
    return initial
