from dataclasses import dataclass

from replay.rationals import require_positive_int


@dataclass(frozen=True, order=True)
class ClosedWindow:
    first: int
    last: int

    def contains(self, row_no):
        return self.first <= row_no <= self.last


def _checked_window(item):
    if isinstance(item, ClosedWindow):
        first, last = item.first, item.last
    elif isinstance(item, (tuple, list)) and len(item) == 2:
        first, last = item
    else:
        raise ValueError('each closed window requires two endpoints')
    require_positive_int(first, 'first window endpoint')
    require_positive_int(last, 'last window endpoint')
    if first > last:
        raise ValueError('closed window endpoints are reversed')
    return ClosedWindow(first, last)


def normalize_windows(windows):
    try:
        items = iter(windows)
    except TypeError as exc:
        raise ValueError('expected one or two closed windows') from exc
    normalized = []
    for item in items:
        if len(normalized) == 2:
            raise ValueError('expected one or two closed windows')
        normalized.append(_checked_window(item))
    if not normalized:
        raise ValueError('expected one or two closed windows')
    normalized.sort()
    if len(normalized) == 2 and normalized[1].first <= normalized[0].last:
        raise ValueError('closed windows overlap')
    return tuple(normalized)


def select_rows(rows, windows):
    """Return one-based source positions for normalized windows, in source order."""
    selected = []
    hit_windows = set()
    for position, row in enumerate(rows, start=1):
        for window in windows:
            if window.contains(row.row_no):
                selected.append(position)
                hit_windows.add(window)
                break
    if len(hit_windows) != len(windows):
        raise ValueError('each window must select at least one source row')
    return tuple(selected)
