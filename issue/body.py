from dataclasses import dataclass
from fractions import Fraction

from issue.envelope import json_bytes, json_object, require_fields
from issue.windows import ClosedWindow, normalize_windows
from replay.rationals import encode_rational, parse_rational, require_database_id, require_positive_int
from replay.transform import decode_transform
from source.sequence import validate_text


@dataclass(frozen=True)
class WindowRow:
    position: int
    row_no: int
    delta: Fraction
    origin: str


@dataclass(frozen=True)
class WindowSection:
    evidence: str
    rows: tuple[WindowRow, ...]


@dataclass(frozen=True)
class WindowBody:
    roll_id: str
    revision_id: int
    frozen_id: int
    windows: tuple[ClosedWindow, ...]
    sections: tuple[WindowSection, ...]

    def selected_rows(self):
        for section in self.sections:
            yield from section.rows


def _encode_row(row):
    return {
        'position': row.position,
        'row_no': row.row_no,
        'delta': encode_rational(row.delta),
        'origin': row.origin,
    }


def encode_body(body):
    return json_bytes({
        'roll_id': body.roll_id,
        'revision_id': body.revision_id,
        'frozen_id': body.frozen_id,
        'windows': [[window.first, window.last] for window in body.windows],
        'sections': [
            {'evidence': section.evidence, 'rows': [_encode_row(row) for row in section.rows]}
            for section in body.sections
        ],
    })


def _decode_row(record):
    require_fields(record, {'position', 'row_no', 'delta', 'origin'}, 'window row')
    delta = parse_rational(record['delta'])
    if record['delta'] != encode_rational(delta):
        raise ValueError('encoded delta must be a canonical rational string')
    return WindowRow(
        require_positive_int(record['position'], 'source position'),
        require_positive_int(record['row_no'], 'row number'),
        delta,
        validate_text(record['origin'], 'row origin'),
    )


def _decode_section(record):
    require_fields(record, {'evidence', 'rows'}, 'window section')
    evidence = validate_text(record['evidence'], 'section evidence')
    decode_transform(evidence)
    if not isinstance(record['rows'], list) or not record['rows']:
        raise ValueError('a window section must contain selected rows')
    return WindowSection(evidence, tuple(_decode_row(row) for row in record['rows']))


def _validate_layout(windows, sections):
    previously_selected = set()
    covered_windows = set()
    previous_end = -1
    for section in sections:
        first_position = section.rows[0].position
        if first_position <= previous_end + 1:
            raise ValueError('window sections overlap, touch in source order, or are out of order')
        for position, row in enumerate(section.rows, start=first_position):
            if row.position != position:
                raise ValueError('rows in a window section must occupy consecutive source positions')
            if row.row_no in previously_selected:
                raise ValueError('duplicate selected row number')
            previously_selected.add(row.row_no)
            for window in windows:
                if window.contains(row.row_no):
                    covered_windows.add(window)
                    break
            else:
                raise ValueError('selected row is outside the requested windows')
        previous_end = section.rows[-1].position
    if len(covered_windows) != len(windows):
        raise ValueError('package is missing selected rows for a requested window')


def decode_body(raw):
    record = json_object(raw)
    require_fields(record, {'roll_id', 'revision_id', 'frozen_id', 'windows', 'sections'}, 'window body')
    roll_id = validate_text(record['roll_id'], 'roll ID')
    revision_id = require_database_id(record['revision_id'], 'revision ID')
    frozen_id = require_database_id(record['frozen_id'], 'frozen ID')
    if not isinstance(record['windows'], list):
        raise ValueError('window body requires an array of windows')
    windows = normalize_windows(record['windows'])
    if not isinstance(record['sections'], list) or not record['sections']:
        raise ValueError('window body requires at least one section')
    sections = tuple(_decode_section(item) for item in record['sections'])
    _validate_layout(windows, sections)
    return WindowBody(roll_id, revision_id, frozen_id, windows, sections)
