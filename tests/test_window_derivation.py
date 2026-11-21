import json
import random
from fractions import Fraction

from issue.body import decode_body
from issue.envelope import json_bytes, seal_envelope, verify_envelope
from issue.registry import issue
from receipt.intake import receive
from replay.readings import replay
from replay.trace import crop_trace
from replay.transform import IDENTITY, decode_transform, encode_transform
from review.requests import review
from source.freeze import freeze
from source.intake import record
from tests import ProjectCase, line_facts, values


class WindowDerivationTests(ProjectCase):
    def test_offline_matches_full_roll_for_any_initial(self):
        rows = [
            {'row_no': 2, 'delta': '7', 'origin': 'clamp.log:1'},
            {'row_no': 5, 'delta': '-9', 'origin': 'clamp.log:2'},
            {'row_no': 9, 'delta': '4', 'origin': 'clamp.log:3'},
            {'row_no': 11, 'delta': '-6', 'origin': 'clamp.log:4'},
            {'row_no': 14, 'delta': '11/2', 'origin': 'clamp.log:5'},
            {'row_no': 20, 'delta': '-8', 'origin': 'clamp.log:6'},
        ]
        roll = 'clamp-roll'
        frozen = freeze(self.station, roll, record(self.station, roll, rows))
        windows = ((5, 9), (14, 14))
        selected = (5, 9, 14)
        issued = issue(self.station, frozen, windows)
        receipt_id = receive(self.isolation, issued.packet)

        initials = [Fraction(k, 7) for k in range(71)] + [Fraction(0), Fraction(10)]
        expected = {
            initial: line_facts(crop_trace(replay(self.station, frozen, initial), selected))
            for initial in initials
        }
        # The isolation machine only sees the delivered packet and the initial value.
        self.station.close()
        for initial in initials:
            with self.subTest(initial=initial):
                report = review(self.isolation, receipt_id, initial)
                self.assertEqual(line_facts(report.lines), expected[initial])

    def test_clamped_carry_between_windows(self):
        rows = [
            {'row_no': 1, 'delta': '2', 'origin': 'c.log:1'},
            {'row_no': 2, 'delta': '15', 'origin': 'c.log:2'},
            {'row_no': 3, 'delta': '-3', 'origin': 'c.log:3'},
            {'row_no': 4, 'delta': '1', 'origin': 'c.log:4'},
        ]
        roll = 'between-clamp'
        frozen = freeze(self.station, roll, record(self.station, roll, rows))
        issued = issue(self.station, frozen, ((1, 1), (4, 4)))
        receipt_id = receive(self.isolation, issued.packet)
        self.station.close()
        # 0 + 2 = 2; + 15 clamps to 10; - 3 = 7; + 1 = 8.
        report = review(self.isolation, receipt_id, 0)
        self.assertEqual(values(report.lines), (2, 8))

    def test_pre_window_clamp(self):
        rows = [
            {'row_no': 10, 'delta': '5', 'origin': 'p.log:1'},
            {'row_no': 11, 'delta': '-5', 'origin': 'p.log:2'},
            {'row_no': 12, 'delta': '4', 'origin': 'p.log:3'},
            {'row_no': 13, 'delta': '9', 'origin': 'p.log:4'},
            {'row_no': 14, 'delta': '-2', 'origin': 'p.log:5'},
        ]
        roll = 'pre-clamp'
        frozen = freeze(self.station, roll, record(self.station, roll, rows))
        issued = issue(self.station, frozen, ((12, 13),))
        receipt_id = receive(self.isolation, issued.packet)
        # 8 + 5 clamps to 10; - 5 = 5; + 4 = 9; + 9 clamps to 10.
        reference = line_facts(crop_trace(replay(self.station, frozen, 8), (12, 13)))
        self.assertEqual(reference, ((12, 9, 'p.log:3'), (13, 10, 'p.log:4')))
        self.station.close()
        self.assertEqual(line_facts(review(self.isolation, receipt_id, 8).lines), reference)

    def test_omitted_rows_and_deltas_remain_at_station(self):
        revision_id, frozen_id = self.prepare()
        source_before = self.source_counts()
        issued = issue(self.station, frozen_id, self.windows)
        # Issuing must not drop or rewrite the station's full source ledger.
        self.assertEqual(self.source_counts(), source_before)
        body = decode_body(verify_envelope(issued.packet).body)
        selected = tuple(body.selected_rows())
        self.assertEqual([(row.position, row.row_no) for row in selected], [(3, 3), (6, 6)])
        selected_deltas = {row.row_no for row in selected}
        self.assertEqual(selected_deltas, {3, 6})
        self.assertEqual(
            self.station.execute(
                'SELECT count(*) FROM source_rows WHERE revision_id = ?', (revision_id,)
            ).fetchone()[0],
            len(self.rows),
        )

    def test_tampered_evidence_rejected(self):
        _, frozen_id = self.prepare()
        issued = issue(self.station, frozen_id, self.windows)
        self.station.close()
        original = verify_envelope(issued.packet).body
        for evidence in ('0 0', '0 5 0', '0 -1 10', '0 0 11', '0/1 0 10', '0 0 10 1', ''):
            with self.subTest(evidence=evidence):
                body = json.loads(original)
                body['sections'][0]['evidence'] = evidence
                packet = seal_envelope(issued.issuance_id, json_bytes(body))
                with self.assertRaises(ValueError):
                    receive(self.isolation, packet)
        self.assertEqual(self.receipt_count(), 0)
        self.assertEqual(self.report_counts(), (0, 0))

    def test_transform_composition_matches_row_by_row_clamping(self):
        rand = random.Random(20261121)
        initials = [Fraction(k, 5) for k in range(51)]
        for _ in range(400):
            deltas = [
                Fraction(rand.randint(-30, 30), rand.choice((1, 2, 3, 7)))
                for _ in range(rand.randint(0, 10))
            ]
            transform = IDENTITY
            for delta in deltas:
                transform = transform.extend(delta)
            self.assertEqual(decode_transform(encode_transform(transform)), transform)
            for initial in initials:
                expected = initial
                for delta in deltas:
                    expected = min(Fraction(10), max(Fraction(0), expected + delta))
                self.assertEqual(transform.apply(initial), expected)
