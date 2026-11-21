import json
import sys
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from demo import load_sample
from init_project import initialize_project
from issue.registry import issue
from receipt.intake import receive
from receipt.storage import open_isolation_db
from replay.readings import replay
from replay.trace import crop_trace
from review.history import get
from review.requests import review
from source.freeze import freeze
from source.intake import record
from source.store import open_source_db


def line_facts(lines):
    return [(line.row_no, str(line.value), line.origin) for line in lines]


def cases(rows):
    lower_first = [dict(row) for row in rows[:3]]
    lower_first[0]["delta"], lower_first[1]["delta"] = "-8", "8"
    carry_only = [dict(row, delta=delta) for row, delta in zip(
        rows, ("0", "0", "-1", "1", "0", "1"), strict=True,
    )]
    return (
        ("shift", rows, ((3, 3), (6, 6)), [(3, "4", "bench-a.log:103"), (6, "5", "bench-a.log:106")]),
        ("upper-first", rows[:3], ((3, 3),), [(3, "4", "bench-a.log:103")]),
        ("lower-first", lower_first, ((3, 3),), [(3, "10", "bench-a.log:103")]),
        ("carry", carry_only, ((3, 3), (6, 6)), [(3, "4", "bench-a.log:103"), (6, "6", "bench-a.log:106")]),
    )


def main():
    sample = load_sample()
    roll_id = sample["roll_id"]
    deliveries = []
    mismatches = 0
    with TemporaryDirectory(prefix="bench-incident-") as directory:
        station_path = Path(directory) / "station.sqlite"
        isolation_path = Path(directory) / "isolation.sqlite"
        initialize_project(station_path, isolation_path)
        with closing(open_source_db(station_path)) as station:
            for name, rows, windows, expected in cases(sample["rows"]):
                case_roll = f"{roll_id}-{name}"
                revision = record(station, case_roll, rows)
                frozen = freeze(station, case_roll, revision)
                trace = replay(station, frozen, 5)
                reference = line_facts(crop_trace(trace, (row[0] for row in expected)))
                if reference != expected:
                    raise RuntimeError(f"{name}: full replay {reference!r}, expected {expected!r}")
                issued = issue(station, frozen, windows)
                deliveries.append((name, issued, reference))
        with closing(open_isolation_db(isolation_path)) as isolation:
            for name, issued, reference in deliveries:
                receipt = receive(isolation, issued.packet)
                report = review(isolation, receipt, 5)
                saved = get(isolation, report.report_id)
                if saved != report:
                    raise RuntimeError(f"{name}: stored report differs from returned report")
                actual = line_facts(saved.lines)
                print(json.dumps({"case": name, "expected": reference, "actual": actual}), flush=True)
                if actual != reference:
                    mismatches += 1
    if mismatches:
        print(f"WINDOW_STATE_MISMATCH cases={mismatches}", file=sys.stderr)
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
