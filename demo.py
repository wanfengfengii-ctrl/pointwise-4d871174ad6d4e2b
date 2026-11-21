import json
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from init_project import initialize_project
from issue.registry import get_issued_package, issue
from receipt.intake import receive
from receipt.storage import open_isolation_db
from replay.readings import replay
from replay.trace import crop_trace
from review.history import get
from review.requests import review
from source.freeze import freeze
from source.intake import record
from source.store import open_source_db


_WINDOWS = ((3, 3), (6, 6))


def load_sample():
    path = Path(__file__).resolve().parent / 'samples' / 'shift.json'
    return json.loads(path.read_text(encoding='utf-8'))


def _display_lines(lines):
    return [[line.row_no, str(line.value), line.origin] for line in lines]


def _require(actual, expected, marker):
    if actual != expected:
        raise SystemExit(f'{marker} expected={expected!r} actual={actual!r}')


def _scenario(case_id, inputs, expected, actual, saved, code_paths, oracle):
    print('POINTWISE_SCENARIO ' + json.dumps({
        'case_id': case_id,
        'input': inputs,
        'expected': expected,
        'actual': actual,
        'downstream_expected': expected,
        'downstream_actual': saved,
        'code_paths': code_paths,
        'oracle': oracle,
    }, sort_keys=True))


def main():
    sample = load_sample()
    roll_id, rows = sample['roll_id'], sample['rows']
    first_lines = [[3, '4', 'bench-a.log:103'], [6, '5', 'bench-a.log:106']]
    expected_full = ['10', '2', '4', '10', '4', '5']
    inputs = {'roll_id': roll_id, 'rows': rows, 'windows': _WINDOWS, 'initial': '5'}
    with TemporaryDirectory(prefix='bench-records-') as directory:
        station_path = Path(directory) / 'station.sqlite'
        isolation_path = Path(directory) / 'isolation.sqlite'
        initialize_project(station_path, isolation_path)

        with closing(open_source_db(station_path)) as station:
            revision = record(station, roll_id, rows)
            frozen = freeze(station, roll_id, revision)
            trace = replay(station, frozen, 5)
            full = [str(line.value) for line in trace.readings]
            _require(full, expected_full, 'FULL_TRACE_MISMATCH')
            cropped = _display_lines(crop_trace(trace, (3, 6)))
            _require(cropped, first_lines, 'TRACE_CROP_MISMATCH')
            issued = issue(station, frozen, _WINDOWS)
            delivered = get_issued_package(station, issued.issuance_id)
            _require(delivered, issued, 'REISSUE_MISMATCH')

        with closing(open_isolation_db(isolation_path)) as isolation:
            receipt_id = receive(isolation, delivered.packet)
            _require(receive(isolation, delivered.packet), receipt_id, 'REDELIVERY_MISMATCH')
            old = review(isolation, receipt_id, 5)
            displayed = _display_lines(old.lines)
            _require(displayed, first_lines, 'WINDOW_STATE_MISMATCH')
            saved = get(isolation, old.report_id)
            _require(saved, old, 'REPORT_HISTORY_MISMATCH')
            _require(
                (saved.receipt_id, saved.frozen_id, saved.revision_id, saved.issuance_id),
                (receipt_id, frozen, revision, issued.issuance_id),
                'REPORT_PARENT_MISMATCH',
            )
            _scenario(
                'v3', inputs, first_lines, displayed, _display_lines(saved.lines),
                ['replay/readings.py', 'issue/evidence.py', 'review/evaluate.py', 'review/history.py'],
                'Hand calculation: 10, 2, 4, 10, 4, 5 after each clamp; keep rows 3 and 6.',
            )

            expected_pairs = [['2', '5'], ['5/2', '5']]
            reports = [review(isolation, receipt_id, initial) for initial in ('0', '1/2')]
            pairs = [[str(line.value) for line in report.lines] for report in reports]
            _require(pairs, expected_pairs, 'WINDOW_STATE_MISMATCH')
            persisted = [get(isolation, report.report_id) for report in reports]
            _require(persisted, reports, 'REPORT_HISTORY_MISMATCH')
            _require([report.receipt_id for report in persisted], [receipt_id] * 2, 'REPORT_PARENT_MISMATCH')
            _scenario(
                'v6', {**inputs, 'initial': ['0', '1/2']}, expected_pairs, pairs,
                [[str(line.value) for line in report.lines] for report in persisted],
                ['receipt/storage.py', 'review/requests.py', 'review/evaluate.py', 'review/publish.py'],
                'With 0 or 1/2 the first two adjustments cancel; row 4 reaches 10 in both cases.',
            )

        corrected_rows = [dict(row) for row in rows]
        corrected_rows[2]['delta'] = '3'
        with closing(open_source_db(station_path)) as station:
            correction = record(station, roll_id, corrected_rows, parent_revision_id=revision)
            corrected_frozen = freeze(station, roll_id, correction)
            new_issue = issue(station, corrected_frozen, _WINDOWS)
            _require(replay(station, frozen, 5), trace, 'FROZEN_REVISION_MISMATCH')

        with closing(open_isolation_db(isolation_path)) as isolation:
            new_receipt = receive(isolation, new_issue.packet)
            new = review(isolation, new_receipt, 5)
        with closing(open_isolation_db(isolation_path)) as isolation:
            archived = [get(isolation, report.report_id) for report in (old, new)]
        expected_history = [first_lines, [[3, '5', 'bench-a.log:103'], [6, '5', 'bench-a.log:106']]]
        signed_lines = [_display_lines(report.lines) for report in (old, new)]
        _require(signed_lines, expected_history, 'REPORT_CORRECTION_MISMATCH')
        _require(archived, [old, new], 'REPORT_HISTORY_MISMATCH')
        _require(
            (new.receipt_id, new.frozen_id, new.revision_id, new.issuance_id),
            (new_receipt, corrected_frozen, correction, new_issue.issuance_id),
            'REPORT_PARENT_MISMATCH',
        )
        _scenario(
            'v8', {**inputs, 'corrected_rows': corrected_rows}, expected_history, signed_lines,
            [_display_lines(report.lines) for report in archived],
            ['source/revisions.py', 'source/freeze.py', 'review/publish.py', 'review/history.py'],
            'Row 3 increases from 4 to 5; row 4 still reaches 10, so row 6 stays at 5.',
        )


if __name__ == '__main__':
    main()
