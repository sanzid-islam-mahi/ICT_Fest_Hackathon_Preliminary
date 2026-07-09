"""Human-facing booking reference codes.

Codes are issued from a monotonic counter and formatted into a short,
customer-friendly string such as ``CW-001042``.
"""
import threading

from sqlalchemy.orm import Session

from ..models import Booking

_counter = {"value": 1000}
_lock = threading.Lock()


def next_reference_code() -> str:
    with _lock:
        current = _counter["value"]
        _counter["value"] = current + 1
    return f"CW-{current:06d}"


def reseed_from_db(db: Session) -> None:
    with _lock:
        max_value = 999
        for (reference_code,) in db.query(Booking.reference_code).all():
            if not reference_code.startswith("CW-"):
                continue
            try:
                suffix = int(reference_code[3:])
            except ValueError:
                continue
            if suffix > max_value:
                max_value = suffix
        _counter["value"] = max(1000, max_value + 1)
