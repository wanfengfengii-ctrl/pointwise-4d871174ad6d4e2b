import re
from fractions import Fraction


_RATIONAL_TEXT = re.compile(r'[+-]?[0-9]+(?:/[+-]?[0-9]+|\.[0-9]+)?')


def parse_rational(value):
    if isinstance(value, Fraction):
        return value
    if type(value) is int:
        return Fraction(value)
    if isinstance(value, str):
        text = value.strip()
        if _RATIONAL_TEXT.fullmatch(text):
            try:
                if '/' in text:
                    numerator, denominator = text.split('/')
                    return Fraction(int(numerator), int(denominator))
                return Fraction(text)
            except (ValueError, ZeroDivisionError) as exc:
                raise ValueError(f'invalid rational value {value!r}') from exc
    raise ValueError('expected an integer, Fraction or rational string')


def encode_rational(value):
    return str(parse_rational(value))


def require_positive_int(value, label):
    if type(value) is not int or value < 1:
        raise ValueError(f'{label} must be a positive integer')
    return value


def require_database_id(value, label):
    value = require_positive_int(value, label)
    if value >= 1 << 63:
        raise ValueError(f'{label} exceeds the SQLite identifier range')
    return value
