import base64
import json
from fractions import Fraction

from issue.envelope import json_bytes, verify_envelope
from issue.registry import get_issued_package, issue
from receipt.intake import receive
from receipt.storage import load_receipt
from replay.readings import replay
from replay.trace import crop_trace
from review.history import get
from review.requests import review
from tests import ProjectCase, line_facts, values


class HandoffTests(ProjectCase):
    def test_two_windows_offline(self):
        revision_id, frozen_id = self.prepare()
        full = crop_trace(replay(self.station, frozen_id, 5), (3, 6))
        issued, receipt_id = self.deliver(frozen_id)
        receipt = load_receipt(self.isolation, receipt_id)
        selected = tuple(receipt.delivery.body.selected_rows())
        self.assertEqual([(row.position, row.row_no, row.origin) for row in selected], [
            (3, 3, 'bench-a.log:103'), (6, 6, 'bench-a.log:106'),
        ])
        self.station.close()
        report = review(self.isolation, receipt_id, 5)
        self.assertEqual(line_facts(report.lines), ((3, 4, 'bench-a.log:103'), (6, 5, 'bench-a.log:106')))
        self.assertEqual(line_facts(report.lines), line_facts(full))
        self.assertEqual((report.receipt_id, report.revision_id, report.frozen_id, report.issuance_id),
                         (receipt_id, revision_id, frozen_id, issued.issuance_id))
        self.assertEqual(get(self.isolation, report.report_id), report)

    def test_touching_closed_windows(self):
        _, frozen_id = self.prepare()
        with self.assertRaisesRegex(ValueError, 'overlap'):
            issue(self.station, frozen_id, [(2, 3), (3, 4)])
        self.assertEqual(self.issue_count(), 0)
        _, receipt_id = self.deliver(frozen_id, [(2, 2), (3, 4)])
        self.station.close()
        self.assertEqual(values(review(self.isolation, receipt_id, 5).lines), (2, 4, 10))

    def test_empty_window(self):
        _, frozen_id = self.prepare()
        for invalid in ([], [(10, 12)], [(4, 3)], [(2, 2), (10, 12)], [(1, 1), (2, 2), (3, 3)]):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                issue(self.station, frozen_id, invalid)
        self.assertEqual(self.issue_count(), 0)

    def test_corrupt_receipt(self):
        _, frozen_id = self.prepare()
        _, old_receipt = self.deliver(frozen_id)
        old = review(self.isolation, old_receipt, 5)
        other = issue(self.station, frozen_id, self.windows)
        content = json.loads(other.packet)
        body = json.loads(verify_envelope(other.packet).body)
        body['sections'][0]['rows'][0]['delta'] = '3'
        content['body'] = base64.b64encode(json_bytes(body)).decode('ascii')
        self.station.close()
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            receive(self.isolation, json_bytes(content))
        self.assertEqual(self.receipt_count(), 1)
        self.assertEqual(self.report_counts(), (1, 2))
        self.assertEqual(get(self.isolation, old.report_id), old)
        self.assertEqual(values(review(self.isolation, old_receipt, 5).lines), (4, 5))

    def test_same_packet_two_initial_values(self):
        _, frozen_id = self.prepare()
        _, receipt_id = self.deliver(frozen_id)
        self.station.close()
        zero = review(self.isolation, receipt_id, 0)
        half = review(self.isolation, receipt_id, '1/2')
        self.assertEqual(values(zero.lines), (2, 5))
        self.assertEqual(values(half.lines), (Fraction(5, 2), 5))
        self.assertEqual((zero.initial, half.initial), (Fraction(0), Fraction(1, 2)))
        self.assertEqual((zero.receipt_id, half.receipt_id), (receipt_id, receipt_id))
        self.assertNotEqual(zero.report_id, half.report_id)
        self.assertEqual(get(self.isolation, half.report_id), half)

    def test_window_order(self):
        _, frozen_id = self.prepare()
        _, forward = self.deliver(frozen_id)
        _, reversed_order = self.deliver(frozen_id, self.windows[::-1])
        self.station.close()
        expected = ((3, 4, 'bench-a.log:103'), (6, 5, 'bench-a.log:106'))
        for receipt_id in (forward, reversed_order):
            self.assertEqual(line_facts(review(self.isolation, receipt_id, 5).lines), expected)

    def test_reissue_bytes(self):
        _, frozen_id = self.prepare()
        issued = issue(self.station, frozen_id, self.windows)
        self.station.close()
        self.station = self.open_station()
        copy = get_issued_package(self.station, issued.issuance_id)
        with self.assertRaises(LookupError):
            get_issued_package(self.station, '0' * 32)
        self.station.close()
        self.assertEqual(copy, issued)
        receipt_id = receive(self.isolation, copy.packet)
        self.assertEqual(values(review(self.isolation, receipt_id, 5).lines), (4, 5))

    def test_ordered_prefix(self):
        first = [dict(row) for row in self.rows[:3]]
        second = [dict(row) for row in first]
        second[0]['delta'], second[1]['delta'] = '-8', '8'
        comparisons = []
        for roll, rows in (('upper-first', first), ('lower-first', second)):
            _, frozen_id = self.prepare(rows=rows, roll_id=roll)
            reference = crop_trace(replay(self.station, frozen_id, 5), (3,))
            _, receipt_id = self.deliver(frozen_id, [(3, 3)])
            comparisons.append((receipt_id, reference))
        self.station.close()
        for (receipt_id, reference), expected in zip(comparisons, (4, 10), strict=True):
            report = review(self.isolation, receipt_id, 5)
            self.assertEqual(line_facts(report.lines), ((3, expected, 'bench-a.log:103'),))
            self.assertEqual(line_facts(report.lines), line_facts(reference))

    def test_window_carry(self):
        rows = [dict(row) for row in self.rows]
        rows[3]['delta'], rows[4]['delta'] = '1', '0'
        _, frozen_id = self.prepare(rows=rows)
        expected = ((3, 4, 'bench-a.log:103'), (6, 6, 'bench-a.log:106'))
        self.assertEqual(line_facts(crop_trace(replay(self.station, frozen_id, 5), (3, 6))), expected)
        _, receipt_id = self.deliver(frozen_id)
        self.station.close()
        self.assertEqual(line_facts(review(self.isolation, receipt_id, 5).lines), expected)

    def test_third_initial(self):
        _, frozen_id = self.prepare()
        expected = ((2, 5), (Fraction(5, 2), 5), (4, 5))
        initials = (0, Fraction(1, 2), 5)
        references = [crop_trace(replay(self.station, frozen_id, value), (3, 6)) for value in initials]
        _, receipt_id = self.deliver(frozen_id)
        self.station.close()
        for initial, pair, reference in zip(initials, expected, references, strict=True):
            with self.subTest(initial=initial):
                report = review(self.isolation, receipt_id, initial)
                self.assertEqual((report.receipt_id, report.initial), (receipt_id, initial))
                self.assertEqual(values(report.lines), pair)
                self.assertEqual(line_facts(report.lines), line_facts(reference))

    def test_invalid_request(self):
        _, frozen_id = self.prepare()
        _, receipt_id = self.deliver(frozen_id)
        self.station.close()
        prior = review(self.isolation, receipt_id, 5)
        with self.assertRaises(LookupError):
            review(self.isolation, receipt_id + 90, 5)
        for invalid in (0.5, True, None, '1/0', '-1/2', '21/2'):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                review(self.isolation, receipt_id, invalid)
        self.assertEqual(self.report_counts(), (1, 2))
        self.assertEqual(get(self.isolation, prior.report_id), prior)
