from dataclasses import dataclass
from fractions import Fraction

from replay.limits import LOWER_LIMIT, UPPER_LIMIT, clamp_reading
from replay.rationals import encode_rational, parse_rational


@dataclass(frozen=True)
class Transform:
    """Composition of ``advance_reading`` steps: ``min(high, max(low, value + shift))``.

    The composition of clamped additions is closed under this form, so every run of
    source rows that stays at the station can be represented by one exact transform.
    """

    shift: Fraction
    low: Fraction
    high: Fraction

    def apply(self, value):
        return min(self.high, max(self.low, value + self.shift))

    def extend(self, delta):
        return Transform(
            self.shift + delta,
            clamp_reading(self.low + delta),
            clamp_reading(self.high + delta),
        )


IDENTITY = Transform(Fraction(0), LOWER_LIMIT, UPPER_LIMIT)


def encode_transform(transform):
    return ' '.join(
        encode_rational(part) for part in (transform.shift, transform.low, transform.high)
    )


def decode_transform(value, label='section evidence'):
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f'{label} must be canonical text')
    parts = value.split(' ')
    if len(parts) != 3:
        raise ValueError(f'{label} must contain three canonical rationals')
    try:
        shift, low, high = (parse_rational(part) for part in parts)
    except ValueError as exc:
        raise ValueError(f'{label} must contain canonical rationals') from exc
    transform = Transform(shift, low, high)
    if encode_transform(transform) != value:
        raise ValueError(f'{label} must contain canonical rationals')
    if not LOWER_LIMIT <= low <= high <= UPPER_LIMIT:
        raise ValueError(f'{label} bounds must lie inside [0, 10]')
    return transform
