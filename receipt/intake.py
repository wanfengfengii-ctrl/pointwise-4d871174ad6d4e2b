from receipt.inspect import inspect_delivery
from receipt.storage import store_receipt


def receive(db, packet):
    delivery = inspect_delivery(packet)
    return store_receipt(db, delivery).receipt_id
