from receipt.storage import load_receipt
from replay.validate import validate_initial_value
from review.details import build_draft
from review.evaluate import evaluate_window
from review.history import StoredReport
from review.publish import publish_report


def review(db, receipt_id, initial_value):
    initial = validate_initial_value(initial_value)
    receipt = load_receipt(db, receipt_id)
    readings = evaluate_window(receipt.delivery.body, initial)
    draft = build_draft(receipt, initial, readings)
    report_id = publish_report(db, draft)
    return StoredReport.from_draft(draft, report_id)
