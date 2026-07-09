# Bug Report

## Bug 1 — Token Revocation Checks `sub` Instead of `jti`

- **File:** `app/auth.py`, line 97
- **What the bug was:** `revoke_access_token()` stores the token's `jti` (unique token ID) into `_revoked_tokens`, but `get_token_payload()` checked `payload.get("sub")` (the user ID) against the revoked set. Since a user ID will never match a JTI, logout never actually invalidated the token. Any logged-out token could still be used indefinitely.
- **How it was fixed:** Changed `payload.get("sub")` to `payload.get("jti")` so the revocation check matches what was actually stored.

```diff
- if payload.get("sub") in _revoked_tokens:
+ if payload.get("jti") in _revoked_tokens:
```

---

## Bug 2 — Access Token Expiry 900× Too Long

- **File:** `app/auth.py`, line 50
- **What the bug was:** `ACCESS_TOKEN_EXPIRE_MINUTES` is set to `15` in config.py. The code multiplied it by 60 again: `timedelta(minutes=15 * 60)` = `timedelta(minutes=900)` = 54,000 seconds. The spec requires access tokens to expire in exactly 900 seconds (15 minutes).
- **How it was fixed:** Removed the `* 60` multiplier.

```diff
- lifetime = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES * 60)
+ lifetime = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
```

---

## Bug 3 — Booking List Sorted Descending Instead of Ascending

- **File:** `app/routers/bookings.py`, line 137
- **What the bug was:** The spec (Rule 11) requires bookings sorted ascending by `start_time`. The code used `.desc()`, returning newest bookings first instead of oldest first. This also breaks sequential pagination (pages skip/repeat items when combined with the offset bug).
- **How it was fixed:** Changed `.desc()` to `.asc()`.

```diff
- base.order_by(Booking.start_time.desc(), Booking.id.asc())
+ base.order_by(Booking.start_time.asc(), Booking.id.asc())
```

---

## Bug 4 — Pagination Offset Wrong (`page * limit` instead of `(page - 1) * limit`)

- **File:** `app/routers/bookings.py`, line 138
- **What the bug was:** Pages are 1-indexed (default `page=1`). Using `offset(page * limit)` meant page 1 skipped the first `limit` items entirely. For example, with 5 bookings and `page=1, limit=10`, the offset was 10, so `items` returned empty despite `total` being 5.
- **How it was fixed:** Changed to `(page - 1) * limit` so page 1 has offset 0.

```diff
- .offset(page * limit)
+ .offset((page - 1) * limit)
```

---

## Bug 5 — `get_booking` Overwrites `start_time` with `created_at`

- **File:** `app/routers/bookings.py`, line 166
- **What the bug was:** After `serialize_booking()` correctly populated all fields (including `start_time`), the line `response["start_time"] = iso_utc(booking.created_at)` silently replaced the booking's scheduled start time with the creation timestamp. If a room was booked for tomorrow at 2 PM, the API returned today's creation time as `start_time`.
- **How it was fixed:** Removed the erroneous overwrite line.

```diff
  response = serialize_booking(booking)
- response["start_time"] = iso_utc(booking.created_at)
  response["refunds"] = [
```

## Bug 6 — Duplicate username returns 201 instead of 409 

**File(s):** `app/routers/auth.py:37-43`

**Bug:** When a user attempted to register with a username that already existed within the same organization, the endpoint returned HTTP 201 with the existing user's data instead of raising an error. Per spec section 15: "A duplicate username within the org → 409 USERNAME TAKEN."

**Why it was wrong:** The API silently swallowed duplicate registrations, making it impossible for clients to detect that the username was taken. A user could believe their registration succeeded when in fact no new account was created.

**Fix:** Replaced the `return` block with `raise AppError(409, "USERNAME_TAKEN", "Username already taken in this organization")`.

---

## Bug 7 — Pagination Limit Hardcoded to 10

- **File:** `app/routers/bookings.py`, line 139
- **What the bug was:** The `list_bookings` endpoint accepts a `limit` query parameter (default 10, max 100), but the actual SQL query had `.limit(10)` hardcoded instead of using the user-provided `limit` variable. So requesting `?limit=50` still only returned 10 items.
- **How it was fixed:** Changed `.limit(10)` to `.limit(limit)`.

```diff
- .limit(10)
+ .limit(limit)
```

---

## Bug 8 — Missing Minimum Duration and `end <= start` Validation

- **File:** `app/routers/bookings.py`, lines 89-94
- **What the bug was:** The spec (Rule 2) requires: duration is a whole number of hours, minimum 1, maximum 8, and `end_time` must be strictly after `start_time`. The code only checked that duration is a whole number and that it doesn't exceed 8. It never rejected `end <= start` (zero or negative duration) and never checked `duration < 1`. A booking with `end_time == start_time` (0 hours) or `end_time` before `start_time` would pass validation.
- **How it was fixed:** Added an explicit `end <= start` check that returns 400, and changed the range check to `duration_hours < 1 or duration_hours > 8`.

```diff
+ if end <= start:
+     raise AppError(400, "INVALID_BOOKING_WINDOW", "end_time must be after start_time")
+
  duration_hours = (end - start).total_seconds() / 3600
  ...
- if duration_hours > MAX_DURATION_HOURS:
+ if duration_hours < MIN_DURATION_HOURS or duration_hours > MAX_DURATION_HOURS:
      raise AppError(400, "INVALID_BOOKING_WINDOW", "duration out of range")
```

---

## Bug 9 — Availability Cache Not Invalidated on Cancel

- **File:** `app/routers/bookings.py`, line 217
- **What the bug was:** When a booking is created, `cache.invalidate_availability(room.id, ...)` is correctly called. But when a booking is cancelled, only `cache.invalidate_report()` is called — availability cache is never cleared. The spec (Rule 13) says availability must "reflect the current state immediately." After cancellation, `GET /rooms/{id}/availability` could still show the cancelled booking as a busy slot until the cache expired or the server restarted.
- **How it was fixed:** Added `cache.invalidate_availability(booking.room_id, booking.start_time.date().isoformat())` after cancel.

```diff
  cache.invalidate_report(user.org_id)
+ cache.invalidate_availability(booking.room_id, booking.start_time.date().isoformat())
  notifications.notify_cancelled(booking)
```

---

## Bug 10 — `start_time` Past-Check Has a 5-Minute Grace Window

- **File:** `app/routers/bookings.py`, line 86
- **What the bug was:** The spec (Rule 2) states: "start_time must be strictly in the future at request time — no grace window." The code checked `start <= now - timedelta(seconds=300)`, which only rejected start times more than 5 minutes in the past. A booking with `start_time` equal to `now`, or up to 5 minutes in the past, would pass validation and be committed to the database.
- **How it was fixed:** Changed the condition to `start <= now` so any start time that is not strictly in the future is rejected immediately.

```diff
- if start <= now - timedelta(seconds=300):
+ if start <= now:
      raise AppError(400, "INVALID_BOOKING_WINDOW", "start_time must be in the future")
```

---

## Bug 11 — `_has_conflict` Overlap Condition Uses `<=` Instead of `<`

- **File:** `app/routers/bookings.py`, line 50
- **What the bug was:** The spec (Rule 3) defines overlap as `existing.start < new.end AND new.start < existing.end` — strict less-than on both sides, meaning **back-to-back bookings are allowed**. The code used `<=` on both sides: `b.start_time <= end and start <= b.end_time`. This caused a booking from 2–3 PM to block a new booking starting exactly at 3 PM, returning a false 409 ROOM_CONFLICT.
- **How it was fixed:** Changed both `<=` comparisons to strict `<`.

```diff
- if b.start_time <= end and start <= b.end_time:
+ if b.start_time < end and start < b.end_time:
```

---

## Bug 12 — Refund 48h Boundary Uses Integer Truncation (`notice_hours > 48` instead of `>= 48`)

- **File:** `app/routers/bookings.py`, line 203
- **What the bug was:** The spec (Rule 6) says notice ≥ 48 hours → 100% refund. The code computed `notice_hours = int(notice.total_seconds() // 3600)` (integer floor) and checked `notice_hours > 48` (strictly greater). This means exactly 48 hours of notice got 50% instead of 100%, and e.g. 48h 59m also floored to 48 and fell through to the 50% branch. Both the flooring and the strict `>` were wrong.
- **How it was fixed:** Replaced the integer computation with a direct `timedelta` comparison: `if notice >= timedelta(hours=48)`.

```diff
- notice_hours = int(notice.total_seconds() // 3600)
- if notice_hours > 48:
+ if notice >= timedelta(hours=48):
      refund_percent = 100
```

---

## Bug 13 — Refund for Notice < 24h Returns 50% Instead of 0%

- **File:** `app/routers/bookings.py`, line 208
- **What the bug was:** The spec (Rule 6) states: notice < 24 hours → 0% refund. The `else` branch (covering notice < 24h) incorrectly set `refund_percent = 50`. Cancelling a booking with less than 24 hours notice gave the member a 50% refund instead of nothing.
- **How it was fixed:** Changed `refund_percent = 50` to `refund_percent = 0` in the `else` branch.

```diff
  else:
-     refund_percent = 50
+     refund_percent = 0
```

---

## Bug 14 — Refund Amount Truncated with `int()` and Mismatches Cancel Response

- **Files:** `app/services/refunds.py` lines 15–17; `app/routers/bookings.py` line 210
- **What the bug was (part 1 — wrong rounding):** `log_refund` computed the refund amount as:
  ```python
  dollars = booking.price_cents / 100.0
  refund_dollars = dollars * (percent / 100.0)
  amount_cents = int(refund_dollars * 100)  # truncates toward zero
  ```
  `int()` truncates (floors toward zero), not rounds-half-up. The spec (Rule 6) requires: *"Refund amount rounds to the nearest cent, half-cents rounding up."* For example, 50% of 101 cents = 50.5 cents → `int()` gives 50, but the spec requires 51.

- **What the bug was (part 2 — mismatch):** `cancel_booking` independently calculated `refund_amount_cents = round(booking.price_cents * (refund_percent / 100.0))`, while `log_refund` used `int()`. These two formulas can produce different values. The spec says: *"the amount returned by the cancel response must equal the amount stored in the RefundLog."*

- **How it was fixed:**
  1. Replaced `int()` in `log_refund` with `Decimal` arithmetic and `ROUND_HALF_UP` to match the spec exactly.
  2. Removed the independent `refund_amount_cents` calculation in `cancel_booking`. Instead, `log_refund` now returns the entry, and the cancel response uses `refund_entry.amount_cents` — a single source of truth.

```diff
# app/services/refunds.py
+from decimal import ROUND_HALF_UP, Decimal
 
 def log_refund(db, booking, percent):
-    dollars = booking.price_cents / 100.0
-    refund_dollars = dollars * (percent / 100.0)
-    amount_cents = int(refund_dollars * 100)
+    amount_cents = int(
+        (Decimal(booking.price_cents) * Decimal(percent) / Decimal(100))
+        .quantize(Decimal("1"), rounding=ROUND_HALF_UP)
+    )

# app/routers/bookings.py
-    refund_amount_cents = round(booking.price_cents * (refund_percent / 100.0))
-    log_refund(db, booking, refund_percent)
+    refund_entry = log_refund(db, booking, refund_percent)
     ...
-    "refund_amount_cents": refund_amount_cents,
+    "refund_amount_cents": refund_entry.amount_cents,
```

---

## Bug 15 — Refresh Token Not Invalidated on Use (Single-Use Not Enforced)

- **File:** `app/routers/auth.py`, lines 76–88; `app/auth.py`
- **What the bug was:** The spec (Rule 8) requires refresh tokens to be **single-use**: using a refresh token must invalidate it, and any reuse must return 401. The `/auth/refresh` endpoint called `decode_token()` (which only checks JWT signature and expiry) but never added the presented refresh token's `jti` to `_revoked_tokens`. The same refresh token could be used unlimited times — anyone who intercepted a refresh token had permanent account access until expiry (7 days).
- **How it was fixed:**
  1. Added `is_token_revoked(jti)` to `app/auth.py` to expose a public revocation check.
  2. In the refresh endpoint, check if the token's `jti` is already revoked — if so, raise 401. Then call `revoke_access_token(data)` to invalidate the presented refresh token **before** returning the new token pair.

```diff
# app/auth.py
+def is_token_revoked(jti: str) -> bool:
+    return jti in _revoked_tokens

# app/routers/auth.py
+from ..auth import is_token_revoked, revoke_access_token, ...

 def refresh(payload, db):
     data = decode_token(payload.refresh_token)
     if data.get("type") != "refresh":
         raise AppError(401, ...)
+    if is_token_revoked(data["jti"]):
+        raise AppError(401, "UNAUTHORIZED", "Refresh token has already been used")
     user = db.query(User)...
+    revoke_access_token(data)   # invalidate before returning new tokens
     return { "access_token": ..., "refresh_token": ..., ... }
```
