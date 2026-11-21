from fractions import Fraction

from replay.readings import replay
from replay.trace import crop_trace
from review.requests import review
from source.intake import record
from source.revisions import current_revision, load_revision
from source.sequence import SourceRow
from tests import ProjectCase, line_facts, values


class SequenceContractTests(ProjectCase):
    def test_numeric_windows_preserve_recorded_order(self):
        rows = [
            SourceRow(20, Fraction(8), 'order.log:1'),
            SourceRow(4, Fraction(-8), 'order.log:2'),
            SourceRow(10, Fraction(2), 'order.log:3'),
            SourceRow(2, Fraction(1), 'order.log:4'),
            SourceRow(28, Fraction(1), 'order.log:5'),
        ]
        _, frozen_id = self.prepare(rows=rows)
        reference = crop_trace(replay(self.station, frozen_id, 5), (2, 4, 20, 28))
        _, receipt_id = self.deliver(frozen_id, [(20, 28), (2, 4)])
        self.station.close()
        actual = line_facts(review(self.isolation, receipt_id, 5).lines)
        self.assertEqual(actual, (
            (20, 10, 'order.log:1'), (4, 2, 'order.log:2'),
            (2, 5, 'order.log:4'), (28, 6, 'order.log:5'),
        ))
        self.assertEqual(actual, line_facts(reference))

    def test_bad_rows_preserve_the_accepted_revision(self):
        revision_id, _ = self.prepare()
        before = self.source_counts()
        invalid_rows = (
            {'delta': 3, 'origin': 'a.log:1'},
            {'row_no': 9, 'delta': 3},
            {'row_no': 9, 'delta': 3, 'origin': ' '},
            {'row_no': True, 'delta': 3, 'origin': 'a.log:1'},
            {'row_no': 9, 'delta': 0.5, 'origin': 'a.log:1'},
            {'row_no': 9, 'delta': True, 'origin': 'a.log:1'},
            {'row_no': 9, 'delta': None, 'origin': 'a.log:1'},
            {'row_no': 9, 'delta': '1/0', 'origin': 'a.log:1'},
        )
        for row in invalid_rows:
            with self.subTest(row=row), self.assertRaises(ValueError):
                record(self.station, self.roll_id, [row])
        self.assertEqual(self.source_counts(), before)
        self.assertEqual(current_revision(self.station, self.roll_id).revision_id, revision_id)

    def test_rational_values_round_trip_through_both_ledgers(self):
        rows = [
            {'row_no': 11, 'delta': '2/6', 'origin': 'rational.log:1'},
            {'row_no': 12, 'delta': '-0.125', 'origin': 'rational.log:2'},
        ]
        revision_id, frozen_id = self.prepare(rows=rows)
        revision = load_revision(self.station, revision_id)
        self.assertEqual([row.delta for row in revision.rows], [Fraction(1, 3), Fraction(-1, 8)])
        self.assertEqual(values(replay(self.station, frozen_id, '1/2').readings),
                         (Fraction(5, 6), Fraction(17, 24)))
        _, receipt_id = self.deliver(frozen_id, [(12, 12)])
        self.station.close()
        report = review(self.isolation, receipt_id, '1/2')
        self.assertEqual(line_facts(report.lines), ((12, Fraction(17, 24), 'rational.log:2'),))
