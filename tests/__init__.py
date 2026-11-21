from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from demo import load_sample
from init_project import initialize_project
from issue.registry import issue
from receipt.intake import receive
from receipt.storage import open_isolation_db
from source.freeze import freeze
from source.intake import record
from source.store import open_source_db


class ProjectCase(TestCase):
    def setUp(self):
        directory = TemporaryDirectory(prefix='bench-tests-')
        self.addCleanup(directory.cleanup)
        self.station_path = Path(directory.name) / 'station.sqlite'
        self.isolation_path = Path(directory.name) / 'isolation.sqlite'
        initialize_project(self.station_path, self.isolation_path)
        self.station = self.open_station()
        self.isolation = self.open_isolation()
        sample = load_sample()
        self.roll_id = sample['roll_id']
        self.rows = sample['rows']
        self.windows = ((3, 3), (6, 6))

    def open_station(self):
        db = open_source_db(self.station_path)
        self.addCleanup(db.close)
        return db

    def open_isolation(self):
        db = open_isolation_db(self.isolation_path)
        self.addCleanup(db.close)
        return db

    def prepare(self, rows=None, roll_id=None, parent_revision_id=None):
        roll_id = self.roll_id if roll_id is None else roll_id
        revision_id = record(
            self.station, roll_id, self.rows if rows is None else rows, parent_revision_id
        )
        return revision_id, freeze(self.station, roll_id, revision_id)

    def deliver(self, frozen_id, windows=None):
        issued = issue(self.station, frozen_id, self.windows if windows is None else windows)
        return issued, receive(self.isolation, issued.packet)

    def source_counts(self):
        return (
            self.station.execute('SELECT count(*) FROM revisions').fetchone()[0],
            self.station.execute('SELECT count(*) FROM source_rows').fetchone()[0],
            self.station.execute('SELECT count(*) FROM frozen_revisions').fetchone()[0],
        )

    def receipt_count(self):
        return self.isolation.execute('SELECT count(*) FROM receipts').fetchone()[0]

    def issue_count(self):
        return self.station.execute('SELECT count(*) FROM issued_packages').fetchone()[0]

    def report_counts(self):
        return (
            self.isolation.execute('SELECT count(*) FROM reports').fetchone()[0],
            self.isolation.execute('SELECT count(*) FROM report_lines').fetchone()[0],
        )


def values(lines):
    return tuple(line.value for line in lines)


def line_facts(lines):
    return tuple((line.row_no, line.value, line.origin) for line in lines)
