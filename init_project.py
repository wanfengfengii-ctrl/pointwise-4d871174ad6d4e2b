import argparse
from contextlib import closing
from pathlib import Path

from issue.registry import initialize_issues
from receipt.storage import initialize_receipts, open_isolation_db
from review.publish import initialize_reports
from source.store import initialize_source, open_source_db


def initialize_project(source_path, isolation_path):
    station = Path(source_path)
    isolation = Path(isolation_path)
    same_path = station.resolve() == isolation.resolve()
    same_file = station.exists() and isolation.exists() and station.samefile(isolation)
    if same_path or same_file:
        raise ValueError('station and isolation require different database files')
    with closing(open_source_db(station)) as source_db:
        initialize_source(source_db)
        initialize_issues(source_db)
    with closing(open_isolation_db(isolation)) as isolation_db:
        initialize_receipts(isolation_db)
        initialize_reports(isolation_db)


def main():
    parser = argparse.ArgumentParser(description='Initialize the station and isolation ledgers.')
    parser.add_argument('station', type=Path)
    parser.add_argument('isolation', type=Path)
    args = parser.parse_args()
    initialize_project(args.station, args.isolation)


if __name__ == '__main__':
    main()
