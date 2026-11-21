from enum import Enum


class DeliveryDisposition(Enum):
    FIRST = 'first'
    IDENTICAL = 'identical'
    CONFLICT = 'conflict'


def classify_delivery(previous_packet, delivered_packet):
    if previous_packet is None:
        return DeliveryDisposition.FIRST
    if previous_packet == delivered_packet:
        return DeliveryDisposition.IDENTICAL
    return DeliveryDisposition.CONFLICT
