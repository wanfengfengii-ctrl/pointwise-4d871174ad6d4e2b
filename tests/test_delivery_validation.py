import json
from dataclasses import replace
from fractions import Fraction

from issue.envelope import json_bytes, seal_envelope, verify_envelope
from issue.registry import issue
from receipt.inspect import inspect_delivery
from receipt.intake import receive
from receipt.storage import load_receipt
from review.details import ReportDraft
from review.history import get
from review.publish import publish_report
from review.requests import review
from tests import ProjectCase, line_facts, values


def _body_object(issued):
    return json.loads(verify_envelope(issued.packet).body)


def _with_body(issued, body):
    return seal_envelope(issued.issuance_id, json_bytes(body))


class DeliveryValidationTests(ProjectCase):
    def test_identical_redelivery(self):
        _, frozen_id = self.prepare()
        issued, receipt_id = self.deliver(frozen_id)
        self.station.close()
        old = load_receipt(self.isolation, receipt_id)
        self.isolation.close()
        self.isolation = self.open_isolation()
        self.assertEqual(receive(self.isolation, issued.packet), receipt_id)
        self.assertEqual(self.receipt_count(), 1)
        self.assertEqual(load_receipt(self.isolation, receipt_id), old)
        self.assertEqual(old.delivery.packet, issued.packet)
        self.assertEqual(values(review(self.isolation, receipt_id, 5).lines), (4, 5))

    def test_issuance_collision(self):
        _, frozen_id = self.prepare()
        issued, receipt_id = self.deliver(frozen_id)
        self.station.close()
        body = _body_object(issued)
        body['sections'][0]['rows'][0].update(delta='3', origin='alternate.log:103')
        other_packet = _with_body(issued, body)
        verified = inspect_delivery(other_packet)
        self.assertEqual(verified.issuance_id, issued.issuance_id)
        self.assertEqual(verified.body.sections[0].rows[0].origin, 'alternate.log:103')
        with self.assertRaisesRegex(ValueError, 'conflicting delivery'):
            receive(self.isolation, other_packet)
        self.assertEqual(receive(self.isolation, issued.packet), receipt_id)
        self.assertEqual(self.receipt_count(), 1)
        self.assertEqual(load_receipt(self.isolation, receipt_id).delivery.packet, issued.packet)
        self.assertEqual(line_facts(review(self.isolation, receipt_id, 5).lines), (
            (3, 4, 'bench-a.log:103'), (6, 5, 'bench-a.log:106'),
        ))

    def test_body_shape(self):
        _, frozen_id = self.prepare()
        issued = issue(self.station, frozen_id, self.windows)
        self.station.close()
        for field in ('rows', 'evidence'):
            with self.subTest(field=field):
                body = _body_object(issued)
                del body['sections'][0][field]
                bad_packet = _with_body(issued, body)
                self.assertEqual(verify_envelope(bad_packet).issuance_id, issued.issuance_id)
                with self.assertRaisesRegex(ValueError, 'window section'):
                    receive(self.isolation, bad_packet)
        self.assertEqual(self.receipt_count(), 0)
        self.assertEqual(self.report_counts(), (0, 0))
        self.assertEqual(values(review(self.isolation, receive(self.isolation, issued.packet), 5).lines), (4, 5))

    def test_incomplete_or_misattributed_drafts_are_rejected(self):
        _, frozen_id = self.prepare()
        issued, receipt_id = self.deliver(frozen_id)
        self.station.close()
        good = review(self.isolation, receipt_id, 5)
        draft = ReportDraft(
            good.receipt_id, good.issuance_id, good.roll_id, good.revision_id,
            good.frozen_id, good.initial, good.lines,
        )
        first, second = draft.lines
        invalid = (
            replace(draft, frozen_id=draft.frozen_id + 1),
            replace(draft, initial=Fraction(11)),
            replace(draft, lines=(first,)),
            replace(draft, lines=(second, first)),
            replace(draft, lines=(replace(first, origin='wrong.log:1'), second)),
            replace(draft, lines=(replace(first, value=Fraction(-1)), second)),
        )
        for item in invalid:
            with self.subTest(item=item), self.assertRaises(ValueError):
                publish_report(self.isolation, item)
        self.assertEqual(self.report_counts(), (1, 2))
        self.assertEqual(get(self.isolation, good.report_id), good)
        self.assertEqual(load_receipt(self.isolation, receipt_id).delivery.packet, issued.packet)
