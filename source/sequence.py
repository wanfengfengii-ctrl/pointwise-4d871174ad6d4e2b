from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction

from replay.rationals import parse_rational, require_positive_int


@dataclass(frozen=True)
class SourceRow:
    row_no: int
    delta: Fraction
    origin: str


def validate_text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{label} must be nonblank text')
    value.encode('utf-8')
    return value


def _validated_row(item):
    if isinstance(item, SourceRow):
        row_no, delta, origin = item.row_no, item.delta, item.origin
    elif isinstance(item, Mapping) and item.keys() == {'row_no', 'delta', 'origin'}:
        row_no, delta, origin = item['row_no'], item['delta'], item['origin']
    else:
        raise ValueError('source row requires row_no, delta and origin')
    return SourceRow(
        require_positive_int(row_no, 'row number'),
        parse_rational(delta),
        validate_text(origin, 'row origin'),
    )


def validate_sequence(rows):
    if isinstance(rows, (str, bytes, bytearray, Mapping)):
        raise ValueError('source rows must be a sequence of records')
    try:
        items = iter(rows)
    except TypeError as exc:
        raise ValueError('source rows must be a sequence of records') from exc

    seen = set()
    validated = []
    for item in items:
        row = _validated_row(item)
        if row.row_no in seen:
            raise ValueError(f'duplicate source row {row.row_no}')
        seen.add(row.row_no)
        validated.append(row)
    return tuple(validated)
