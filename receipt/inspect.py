from dataclasses import dataclass

from issue.body import WindowBody, decode_body
from issue.envelope import verify_envelope


@dataclass(frozen=True)
class VerifiedWindow:
    issuance_id: str
    packet: bytes
    body: WindowBody


def inspect_delivery(packet):
    envelope = verify_envelope(packet)
    body = decode_body(envelope.body)
    return VerifiedWindow(envelope.issuance_id, packet, body)
