import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass

from receipt.identity import DeliveryDisposition, classify_delivery
from receipt.inspect import VerifiedWindow, inspect_delivery
from replay.rationals import require_database_id


@dataclass(frozen=True)
class Receipt:
    receipt_id: int
    delivery: VerifiedWindow


def open_isolation_db(path):
    db = sqlite3.connect(path, isolation_level=None)
    db.execute('PRAGMA foreign_keys = ON')
    return db


@contextmanager
def isolation_transaction(db):
    db.execute('BEGIN IMMEDIATE')
    with db:
        yield


def initialize_receipts(db):
    with isolation_transaction(db):
        db.execute('''CREATE TABLE IF NOT EXISTS receipts (
            receipt_id INTEGER PRIMARY KEY,
            issuance_id TEXT NOT NULL UNIQUE,
            packet BLOB NOT NULL
        )''')


def store_receipt(db, delivery):
    with isolation_transaction(db):
        previous = db.execute(
            'SELECT receipt_id, packet FROM receipts WHERE issuance_id = ?',
            (delivery.issuance_id,),
        ).fetchone()
        previous_packet = previous[1] if previous is not None else None
        disposition = classify_delivery(previous_packet, delivery.packet)
        if disposition is DeliveryDisposition.CONFLICT:
            raise ValueError(f'conflicting delivery for issuance {delivery.issuance_id}')
        if disposition is DeliveryDisposition.IDENTICAL:
            receipt_id = previous[0]
        else:
            receipt_id = db.execute(
                'INSERT INTO receipts (issuance_id, packet) VALUES (?, ?)',
                (delivery.issuance_id, delivery.packet),
            ).lastrowid
    return Receipt(receipt_id, delivery)


def load_receipt(db, receipt_id):
    require_database_id(receipt_id, 'receipt ID')
    row = db.execute(
        'SELECT issuance_id, packet FROM receipts WHERE receipt_id = ?', (receipt_id,)
    ).fetchone()
    if row is None:
        raise LookupError(f'unknown receipt {receipt_id}')
    delivery = inspect_delivery(row[1])
    if delivery.issuance_id != row[0]:
        raise ValueError('stored receipt identity does not match its packet')
    return Receipt(receipt_id, delivery)
