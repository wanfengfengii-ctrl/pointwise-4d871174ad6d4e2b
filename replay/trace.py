from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class Reading:
    row_no: int
    value: Fraction
    origin: str


@dataclass(frozen=True)
class ReplayTrace:
    roll_id: str
    revision_id: int
    frozen_id: int
    initial: Fraction
    readings: tuple[Reading, ...]


def crop_trace(trace, row_numbers):
    selected = set(row_numbers)
    return tuple(reading for reading in trace.readings if reading.row_no in selected)
