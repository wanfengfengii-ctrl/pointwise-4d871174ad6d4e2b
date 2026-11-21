from dataclasses import dataclass
from fractions import Fraction

from replay.limits import LOWER_LIMIT, UPPER_LIMIT


@dataclass(frozen=True)
class ReportLine:
    row_no: int
    value: Fraction
    origin: str


@dataclass(frozen=True)
class ReportDraft:
    receipt_id: int
    issuance_id: str
    roll_id: str
    revision_id: int
    frozen_id: int
    initial: Fraction
    lines: tuple[ReportLine, ...]


def build_draft(receipt, initial, readings):
    body = receipt.delivery.body
    draft = ReportDraft(
        receipt.receipt_id,
        receipt.delivery.issuance_id,
        body.roll_id,
        body.revision_id,
        body.frozen_id,
        initial,
        tuple(ReportLine(reading.row_no, reading.value, reading.origin) for reading in readings),
    )
    validate_draft(draft, receipt)
    return draft


def _valid_reading(value):
    return isinstance(value, Fraction) and LOWER_LIMIT <= value <= UPPER_LIMIT


def validate_draft(draft, receipt):
    body = receipt.delivery.body
    if (
        draft.receipt_id != receipt.receipt_id
        or draft.issuance_id != receipt.delivery.issuance_id
        or draft.roll_id != body.roll_id
        or draft.revision_id != body.revision_id
        or draft.frozen_id != body.frozen_id
    ):
        raise ValueError('draft identity does not match its actual receipt')
    if not _valid_reading(draft.initial):
        raise ValueError('draft has an invalid initial reading')
    selected = tuple(body.selected_rows())
    if len(draft.lines) != len(selected):
        raise ValueError('draft is missing or has extra selected lines')
    for line, row in zip(draft.lines, selected, strict=True):
        if type(line.row_no) is not int or (line.row_no, line.origin) != (row.row_no, row.origin):
            raise ValueError('draft lines must match receipt order and provenance')
        if not _valid_reading(line.value):
            raise ValueError('draft line has an invalid reading')
