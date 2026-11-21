from fractions import Fraction

from issue.body import WindowRow, WindowSection
from replay.rationals import encode_rational


def _section(shift, rows):
    return WindowSection(encode_rational(shift), tuple(rows))


def build_sections(rows, selected_positions):
    """Attach the adjustment for each gap to the following selected run."""
    pending = set(selected_positions)
    sections = []
    run = []
    shift = Fraction(0)
    for position, row in enumerate(rows, start=1):
        if position in pending:
            run.append(WindowRow(position, row.row_no, row.delta, row.origin))
            pending.remove(position)
            continue
        if run:
            sections.append(_section(shift, run))
            if not pending:
                return tuple(sections)
            run = []
            shift = Fraction(0)
        shift += row.delta
    if run:
        sections.append(_section(shift, run))
    return tuple(sections)
