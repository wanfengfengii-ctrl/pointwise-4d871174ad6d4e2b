from issue.body import WindowSection, WindowRow
from replay.transform import IDENTITY, encode_transform


def _section(transform, rows):
    return WindowSection(encode_transform(transform), tuple(rows))


def build_sections(rows, selected_positions):
    """Attach the composed clamped transform of each gap to the following selected run.

    Omitted source rows keep their individual adjustments at the station; only the
    exact derived transform (shift and reachable bounds) travels with the package.
    """
    pending = set(selected_positions)
    sections = []
    run = []
    transform = IDENTITY
    for position, row in enumerate(rows, start=1):
        if position in pending:
            run.append(WindowRow(position, row.row_no, row.delta, row.origin))
            pending.remove(position)
            continue
        if run:
            sections.append(_section(transform, run))
            if not pending:
                return tuple(sections)
            run = []
            transform = IDENTITY
        transform = transform.extend(row.delta)
    if run:
        sections.append(_section(transform, run))
    return tuple(sections)
