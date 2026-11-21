from fractions import Fraction

from issue.registry import issue
from replay.readings import replay
from source.freeze import freeze, load_frozen
from source.intake import record
from source.revisions import current_revision, load_revision
from tests import ProjectCase, line_facts, values


class SourceTests(ProjectCase):
    def test_exact_full_replay(self):
        revision_id, frozen_id = self.prepare()
        trace = replay(self.station, frozen_id, 5)
        self.assertEqual((trace.roll_id, trace.revision_id, trace.frozen_id, trace.initial),
                         (self.roll_id, revision_id, frozen_id, Fraction(5)))
        self.assertEqual(line_facts(trace.readings), (
            (1, 10, 'bench-a.log:101'), (2, 2, 'bench-a.log:102'),
            (3, 4, 'bench-a.log:103'), (4, 10, 'bench-a.log:104'),
            (5, 4, 'bench-a.log:105'), (6, 5, 'bench-a.log:106'),
        ))

    def test_initial_bounds(self):
        _, frozen_id = self.prepare()
        for initial, expected in (
            (0, (8, 0, 2, 10, 4, 5)),
            (10, (10, 2, 4, 10, 4, 5)),
            ('1/2', (Fraction(17, 2), Fraction(1, 2), Fraction(5, 2), 10, 4, 5)),
        ):
            with self.subTest(initial=initial):
                self.assertEqual(values(replay(self.station, frozen_id, initial).readings), expected)
        for invalid in ('-1/3', '31/3', 5.0, True, None, '1/0'):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                replay(self.station, frozen_id, invalid)

    def test_empty_revision(self):
        revision_id, frozen_id = self.prepare(rows=[])
        self.assertEqual(load_revision(self.station, revision_id).rows, ())
        self.assertEqual(replay(self.station, frozen_id, 4).readings, ())
        with self.assertRaisesRegex(ValueError, 'at least one source row'):
            issue(self.station, frozen_id, [(1, 1)])
        self.assertEqual(self.issue_count(), 0)

    def test_duplicate_row_rejected(self):
        revision_id, frozen_id = self.prepare()
        original_counts = self.source_counts()
        duplicate = [self.rows[0], {**self.rows[0], 'delta': '1', 'origin': 'second.log:1'}]
        with self.assertRaisesRegex(ValueError, 'duplicate source row'):
            record(self.station, self.roll_id, duplicate, revision_id)
        self.assertEqual(self.source_counts(), original_counts)
        self.assertEqual(current_revision(self.station, self.roll_id).revision_id, revision_id)
        self.assertEqual(values(replay(self.station, frozen_id, 5).readings), (10, 2, 4, 10, 4, 5))

    def test_frozen_revision(self):
        revision_id, frozen_id = self.prepare()
        foreign_revision, _ = self.prepare(roll_id='other-bench')
        before = self.source_counts()
        with self.assertRaisesRegex(ValueError, 'does not belong'):
            record(self.station, self.roll_id, self.rows, foreign_revision)
        with self.assertRaises(LookupError):
            freeze(self.station, self.roll_id, foreign_revision)
        with self.assertRaises(LookupError):
            freeze(self.station, self.roll_id, 1000)
        self.assertEqual(self.source_counts(), before)
        self.assertEqual(current_revision(self.station, self.roll_id).revision_id, revision_id)
        updated = [dict(row) for row in self.rows]
        updated[2]['delta'] = '3'
        new_id, new_frozen = self.prepare(rows=updated)
        self.assertEqual(load_revision(self.station, new_id).parent_revision_id, revision_id)
        self.assertEqual(load_frozen(self.station, frozen_id).revision.revision_id, revision_id)
        self.assertEqual(freeze(self.station, self.roll_id, revision_id), frozen_id)
        self.assertEqual(values(replay(self.station, frozen_id, 5).readings), (10, 2, 4, 10, 4, 5))
        self.assertEqual(values(replay(self.station, new_frozen, 5).readings), (10, 2, 5, 10, 4, 5))
