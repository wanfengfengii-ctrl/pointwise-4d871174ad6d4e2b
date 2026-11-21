from fractions import Fraction


LOWER_LIMIT = Fraction(0)
UPPER_LIMIT = Fraction(10)


def clamp_reading(value):
    return min(UPPER_LIMIT, max(LOWER_LIMIT, value))


def advance_reading(value, delta):
    return clamp_reading(value + delta)
