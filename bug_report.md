# Bug Report

## Bug 1 — Duplicate username returns 201 instead of 409 

**File(s):** `app/routers/auth.py:37-43`

**Bug:** When a user attempted to register with a username that already existed within the same organization, the endpoint returned HTTP 201 with the existing user's data instead of raising an error. Per spec section 15: "A duplicate username within the org → 409 USERNAME TAKEN."

**Why it was wrong:** The API silently swallowed duplicate registrations, making it impossible for clients to detect that the username was taken. A user could believe their registration succeeded when in fact no new account was created.

**Fix:** Replaced the `return` block with `raise AppError(409, "USERNAME_TAKEN", "Username already taken in this organization")`.
