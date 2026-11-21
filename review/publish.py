from receipt.storage import isolation_transaction, load_receipt
from replay.rationals import encode_rational
from review.details import validate_draft


_REPORT_SCHEMA = (
    '''CREATE TABLE IF NOT EXISTS reports (
        report_id INTEGER PRIMARY KEY,
        receipt_id INTEGER NOT NULL REFERENCES receipts (receipt_id),
        issuance_id TEXT NOT NULL,
        roll_id TEXT NOT NULL,
        revision_id INTEGER NOT NULL,
        frozen_id INTEGER NOT NULL,
        initial TEXT NOT NULL
    )''',
    '''CREATE TABLE IF NOT EXISTS report_lines (
        report_id INTEGER NOT NULL REFERENCES reports (report_id),
        ordinal INTEGER NOT NULL CHECK (ordinal > 0),
        row_no TEXT NOT NULL,
        value TEXT NOT NULL,
        origin TEXT NOT NULL,
        PRIMARY KEY (report_id, ordinal),
        UNIQUE (report_id, row_no)
    )''',
    'CREATE INDEX IF NOT EXISTS reports_by_receipt ON reports (receipt_id)',
)


def initialize_reports(db):
    with isolation_transaction(db):
        for statement in _REPORT_SCHEMA:
            db.execute(statement)


def publish_report(db, draft):
    with isolation_transaction(db):
        actual_receipt = load_receipt(db, draft.receipt_id)
        validate_draft(draft, actual_receipt)
        report_id = db.execute(
            '''INSERT INTO reports (receipt_id, issuance_id, roll_id, revision_id, frozen_id, initial)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (
                draft.receipt_id, draft.issuance_id, draft.roll_id, draft.revision_id,
                draft.frozen_id, encode_rational(draft.initial),
            ),
        ).lastrowid
        db.executemany(
            '''INSERT INTO report_lines (report_id, ordinal, row_no, value, origin)
               VALUES (?, ?, ?, ?, ?)''',
            (
                (report_id, ordinal, str(line.row_no), encode_rational(line.value), line.origin)
                for ordinal, line in enumerate(draft.lines, start=1)
            ),
        )
    return report_id
