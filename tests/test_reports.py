import sqlite3

from init_project import initialize_project
from issue.registry import get_issued_package
from receipt.storage import load_receipt
from review.history import get
from review.requests import review
from source.freeze import load_frozen
from source.revisions import current_revision
from tests import ProjectCase, line_facts, values


class ReportTests(ProjectCase):
    def test_publish_rollback(self):
        _, frozen_id = self.prepare()
        _, receipt_id = self.deliver(frozen_id)
        self.station.close()
        old = review(self.isolation, receipt_id, 5)
        denials = []

        def deny_commit(action, argument, _second, _database, _trigger):
            if action == sqlite3.SQLITE_TRANSACTION and argument == 'COMMIT':
                denials.append(argument)
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        self.isolation.set_authorizer(deny_commit)
        try:
            with self.assertRaisesRegex(sqlite3.DatabaseError, 'not authorized'):
                review(self.isolation, receipt_id, 0)
        finally:
            self.isolation.set_authorizer(None)
        self.assertEqual(denials, ['COMMIT'])
        self.assertFalse(self.isolation.in_transaction)
        self.isolation.close()
        self.isolation = self.open_isolation()
        self.assertEqual(self.report_counts(), (1, 2))
        self.assertEqual(get(self.isolation, old.report_id), old)

    def test_partial_commit(self):
        _, frozen_id = self.prepare()
        _, receipt_id = self.deliver(frozen_id)
        self.station.close()
        old = review(self.isolation, receipt_id, 5)
        self.isolation.execute('''CREATE TEMP TRIGGER reject_second_line
            BEFORE INSERT ON report_lines WHEN NEW.ordinal = 2
            BEGIN SELECT RAISE(ABORT, 'second line blocked'); END''')
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'second line blocked'):
            review(self.isolation, receipt_id, '1/2')
        self.isolation.close()
        self.isolation = self.open_isolation()
        self.assertEqual(self.report_counts(), (1, 2))
        self.assertEqual(get(self.isolation, old.report_id), old)
        retried = review(self.isolation, receipt_id, 0)
        self.assertEqual(self.report_counts(), (2, 4))
        self.assertEqual(values(get(self.isolation, retried.report_id).lines), (2, 5))

    def _correct_and_reopen(self, final_row=6):
        rows = [dict(row) for row in self.rows]
        rows[-1]['row_no'] = final_row
        windows = ((3, 3), (final_row, final_row))
        old_revision, old_frozen = self.prepare(rows=rows)
        old_issue, old_receipt = self.deliver(old_frozen, windows)
        self.station.close()
        old = review(self.isolation, old_receipt, 5)

        self.station = self.open_station()
        rows[2]['delta'] = '3'
        new_revision, new_frozen = self.prepare(rows=rows, parent_revision_id=old_revision)
        new_issue, new_receipt = self.deliver(new_frozen, windows)
        self.station.close()
        new = review(self.isolation, new_receipt, 5)
        self.isolation.close()
        self.isolation = self.open_isolation()
        saved_old = get(self.isolation, old.report_id)
        saved_new = get(self.isolation, new.report_id)
        self.assertEqual((saved_old, saved_new), (old, new))
        self.assertEqual((saved_old.revision_id, saved_old.frozen_id, saved_old.receipt_id, saved_old.issuance_id),
                         (old_revision, old_frozen, old_receipt, old_issue.issuance_id))
        self.assertEqual((saved_new.revision_id, saved_new.frozen_id, saved_new.receipt_id, saved_new.issuance_id),
                         (new_revision, new_frozen, new_receipt, new_issue.issuance_id))
        self.assertNotEqual(old.receipt_id, new.receipt_id)
        self.assertEqual(line_facts(saved_old.lines), (
            (3, 4, 'bench-a.log:103'), (final_row, 5, 'bench-a.log:106'),
        ))
        self.assertEqual(line_facts(saved_new.lines), (
            (3, 5, 'bench-a.log:103'), (final_row, 5, 'bench-a.log:106'),
        ))
        return saved_old, saved_new

    def test_old_report_survives_correction(self):
        old, new = self._correct_and_reopen()
        self.assertEqual((values(old.lines), values(new.lines)), ((4, 5), (5, 5)))

    def test_persisted_order(self):
        old, new = self._correct_and_reopen(final_row=10)
        self.assertEqual([line.row_no for line in old.lines], [3, 10])
        self.assertEqual([line.row_no for line in new.lines], [3, 10])

    def test_unknown_report(self):
        old, new = self._correct_and_reopen()
        with self.assertRaises(LookupError):
            get(self.isolation, new.report_id + 90)
        self.assertEqual(get(self.isolation, old.report_id), old)
        self.assertEqual(self.report_counts(), (2, 4))

    def test_reopen_after_init(self):
        old, new = self._correct_and_reopen()
        self.station = self.open_station()
        prior_revision = current_revision(self.station, self.roll_id)
        reports = (old, new)
        frozen = tuple(load_frozen(self.station, report.frozen_id) for report in reports)
        packages = tuple(get_issued_package(self.station, report.issuance_id) for report in reports)
        receipts = tuple(load_receipt(self.isolation, report.receipt_id) for report in reports)
        self.station.close()
        self.isolation.close()
        initialize_project(self.station_path, self.isolation_path)
        initialize_project(self.station_path, self.isolation_path)
        self.station = self.open_station()
        self.isolation = self.open_isolation()
        self.assertEqual(current_revision(self.station, self.roll_id), prior_revision)
        self.assertEqual(prior_revision.parent_revision_id, old.revision_id)
        self.assertEqual(tuple(load_frozen(self.station, report.frozen_id) for report in reports), frozen)
        self.assertEqual(tuple(get_issued_package(self.station, report.issuance_id) for report in reports), packages)
        self.assertEqual(tuple(load_receipt(self.isolation, report.receipt_id) for report in reports), receipts)
        self.assertEqual(tuple(receipt.delivery.packet for receipt in receipts), tuple(p.packet for p in packages))
        self.assertEqual(tuple(get(self.isolation, report.report_id) for report in reports), reports)
        self.assertEqual(self.source_counts(), (2, 12, 2))
        self.assertEqual((self.issue_count(), self.receipt_count(), self.report_counts()), (2, 2, (2, 4)))
