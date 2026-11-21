from dataclasses import dataclass

from replay.rationals import parse_rational, require_database_id
from review.details import ReportDraft, ReportLine


@dataclass(frozen=True)
class StoredReport(ReportDraft):
    report_id: int

    @classmethod
    def from_draft(cls, draft, report_id):
        return cls(
            draft.receipt_id, draft.issuance_id, draft.roll_id, draft.revision_id,
            draft.frozen_id, draft.initial, draft.lines, report_id,
        )


def get(db, report_id):
    require_database_id(report_id, 'report ID')
    head = db.execute(
        '''SELECT receipt_id, issuance_id, roll_id, revision_id, frozen_id, initial
           FROM reports WHERE report_id = ?''',
        (report_id,),
    ).fetchone()
    if head is None:
        raise LookupError(f'unknown report {report_id}')
    receipt_id, issuance_id, roll_id, revision_id, frozen_id, initial = head
    lines = tuple(
        ReportLine(int(row_no), parse_rational(value), origin)
        for row_no, value, origin in db.execute(
            '''SELECT row_no, value, origin FROM report_lines
               WHERE report_id = ? ORDER BY ordinal''',
            (report_id,),
        )
    )
    return StoredReport(
        receipt_id, issuance_id, roll_id, revision_id, frozen_id,
        parse_rational(initial), lines, report_id,
    )
