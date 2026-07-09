"""Live per-room booking statistics.

Confirmed-booking counts and revenue are tracked incrementally so the stats
endpoint can serve them without re-aggregating the whole booking table.
"""
import threading

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import Booking

_stats: dict[int, dict] = {}
_lock = threading.Lock()


def record_create(room_id: int, price_cents: int) -> None:
    with _lock:
        current = _stats.get(room_id, {"count": 0, "revenue": 0})
        count, revenue = current["count"], current["revenue"]
        _stats[room_id] = {"count": count + 1, "revenue": revenue + price_cents}


def record_cancel(room_id: int, price_cents: int) -> None:
    with _lock:
        current = _stats.get(room_id, {"count": 0, "revenue": 0})
        count, revenue = current["count"], current["revenue"]
        _stats[room_id] = {"count": max(0, count - 1), "revenue": revenue - price_cents}


def get(room_id: int) -> dict:
    return _stats.get(room_id, {"count": 0, "revenue": 0})


def rebuild_from_db(db: Session) -> None:
    with _lock:
        _stats.clear()
        rows = (
            db.query(
                Booking.room_id,
                func.count(Booking.id),
                func.coalesce(func.sum(Booking.price_cents), 0),
            )
            .filter(Booking.status == "confirmed")
            .group_by(Booking.room_id)
            .all()
        )
        for room_id, count, revenue in rows:
            _stats[room_id] = {"count": int(count), "revenue": int(revenue)}
