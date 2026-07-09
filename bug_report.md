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


