"""
Seed script to populate the CoWork database with test data at every level.
Run with: python seed.py (while the server is running at localhost:8000)

Creates:
  - 2 organizations (Acme Corp, Globex Inc)
  - 3 users per org (1 admin + 2 members)
  - 2 rooms per org
  - Multiple bookings (confirmed, cancelled, various time slots)
  - Cancellation/refund data

After running, you can use the printed credentials in Postman.
"""
import requests
import json
from datetime import datetime, timedelta, timezone

BASE = "http://localhost:8000"

def pp(label, resp):
    """Pretty-print a response."""
    status = resp.status_code
    try:
        body = json.dumps(resp.json(), indent=2)
    except Exception:
        body = resp.text
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"  Status: {status}")
    print(f"{'='*60}")
    print(body)
    return resp

def future(hours):
    """Return an ISO UTC datetime string `hours` from now, rounded to the hour."""
    dt = (datetime.now(timezone.utc) + timedelta(hours=hours)).replace(
        minute=0, second=0, microsecond=0
    )
    return dt.isoformat()

def register(org_name, username, password="password123"):
    r = requests.post(f"{BASE}/auth/register", json={
        "org_name": org_name, "username": username, "password": password
    })
    pp(f"Register {username}@{org_name}", r)
    return r.json()

def login(org_name, username, password="password123"):
    r = requests.post(f"{BASE}/auth/login", json={
        "org_name": org_name, "username": username, "password": password
    })
    pp(f"Login {username}@{org_name}", r)
    data = r.json()
    return data["access_token"]

def auth(token):
    return {"Authorization": f"Bearer {token}"}

def create_room(token, name, capacity, rate_cents):
    r = requests.post(f"{BASE}/rooms", json={
        "name": name, "capacity": capacity, "hourly_rate_cents": rate_cents
    }, headers=auth(token))
    pp(f"Create room: {name}", r)
    return r.json()

def create_booking(token, room_id, start_hours, duration_hours):
    start = future(start_hours)
    end = future(start_hours + duration_hours)
    r = requests.post(f"{BASE}/bookings", json={
        "room_id": room_id, "start_time": start, "end_time": end
    }, headers=auth(token))
    pp(f"Book room {room_id}: +{start_hours}h for {duration_hours}h", r)
    return r.json()

def cancel_booking(token, booking_id):
    r = requests.post(f"{BASE}/bookings/{booking_id}/cancel", headers=auth(token))
    pp(f"Cancel booking {booking_id}", r)
    return r.json()

def list_bookings(token, page=1, limit=10):
    r = requests.get(f"{BASE}/bookings", params={"page": page, "limit": limit}, headers=auth(token))
    pp(f"List bookings (page={page}, limit={limit})", r)
    return r.json()

def get_booking(token, booking_id):
    r = requests.get(f"{BASE}/bookings/{booking_id}", headers=auth(token))
    pp(f"Get booking {booking_id}", r)
    return r.json()

def list_rooms(token):
    r = requests.get(f"{BASE}/rooms", headers=auth(token))
    pp("List rooms", r)
    return r.json()

def room_availability(token, room_id, date_str):
    r = requests.get(f"{BASE}/rooms/{room_id}/availability", params={"date": date_str}, headers=auth(token))
    pp(f"Availability room {room_id} on {date_str}", r)
    return r.json()

def room_stats(token, room_id):
    r = requests.get(f"{BASE}/rooms/{room_id}/stats", headers=auth(token))
    pp(f"Stats room {room_id}", r)
    return r.json()

def usage_report(token, from_date, to_date):
    r = requests.get(f"{BASE}/admin/usage-report", params={"from": from_date, "to": to_date}, headers=auth(token))
    pp(f"Usage report {from_date} to {to_date}", r)
    return r.json()

def export_csv(token, room_id=None, include_all=False):
    params = {"include_all": str(include_all).lower()}
    if room_id:
        params["room_id"] = room_id
    r = requests.get(f"{BASE}/admin/export", params=params, headers=auth(token))
    pp(f"Export CSV (room_id={room_id}, include_all={include_all})", r)
    return r.text

def health_check():
    r = requests.get(f"{BASE}/health")
    pp("Health check", r)

# ============================================================
#  MAIN SEED LOGIC
# ============================================================
if __name__ == "__main__":
    print("\n" + "🌱"*30)
    print("  CoWork Database Seed Script")
    print("🌱"*30)

    # ---- Health ----
    health_check()

    # ============================================================
    #  ORG 1: Acme Corp
    # ============================================================
    print("\n\n" + "🏢 ORG 1: ACME CORP ".ljust(60, "="))

    # Register users (first user = admin, rest = members)
    reg_alice = register("Acme Corp", "alice")         # admin
    reg_bob   = register("Acme Corp", "bob")           # member
    reg_carol = register("Acme Corp", "carol")         # member

    # Login all users
    token_alice = login("Acme Corp", "alice")
    token_bob   = login("Acme Corp", "bob")
    token_carol = login("Acme Corp", "carol")

    # Create rooms (admin only)
    room1 = create_room(token_alice, "Focus Room", 4, 1000)       # $10/hr
    room2 = create_room(token_alice, "Conference Hall", 20, 2500) # $25/hr

    # ---- Bookings by Bob (member) ----
    # Booking far in future (>48h) — cancellable with 100% refund
    b1 = create_booking(token_bob, room1["id"], 72, 2)   # +72h, 2 hours = $20

    # Booking 30h from now — cancellable with 50% refund
    b2 = create_booking(token_bob, room1["id"], 30, 1)   # +30h, 1 hour = $10

    # Booking 5h from now — cancellable with 0% refund
    b3 = create_booking(token_bob, room2["id"], 5, 3)    # +5h, 3 hours = $75

    # ---- Bookings by Carol (member) ----
    b4 = create_booking(token_carol, room1["id"], 50, 2)  # +50h, 2 hours = $20
    b5 = create_booking(token_carol, room2["id"], 80, 4)  # +80h, 4 hours = $100

    # ---- Cancel one of Bob's bookings (the far-future one for 100% refund) ----
    cancel1 = cancel_booking(token_bob, b1["id"])

    # ---- Admin cancels Carol's booking ----
    cancel2 = cancel_booking(token_alice, b4["id"])

    # ============================================================
    #  ORG 2: Globex Inc
    # ============================================================
    print("\n\n" + "🏢 ORG 2: GLOBEX INC ".ljust(60, "="))

    reg_dave  = register("Globex Inc", "dave")          # admin
    reg_eve   = register("Globex Inc", "eve")           # member
    reg_frank = register("Globex Inc", "frank")         # member

    token_dave  = login("Globex Inc", "dave")
    token_eve   = login("Globex Inc", "eve")
    token_frank = login("Globex Inc", "frank")

    room3 = create_room(token_dave, "War Room", 8, 1500)         # $15/hr
    room4 = create_room(token_dave, "Phone Booth", 1, 500)       # $5/hr

    b6 = create_booking(token_eve, room3["id"], 10, 2)    # +10h, 2 hours
    b7 = create_booking(token_eve, room4["id"], 25, 1)    # +25h, 1 hour
    b8 = create_booking(token_frank, room3["id"], 60, 8)  # +60h, 8 hours (max)
    b9 = create_booking(token_frank, room4["id"], 100, 1) # +100h, 1 hour

    # ============================================================
    #  VALIDATION QUERIES
    # ============================================================
    print("\n\n" + "🔍 VALIDATION QUERIES ".ljust(60, "="))

    # List bookings (pagination test)
    list_bookings(token_bob, page=1, limit=5)

    # Get single booking with refund details
    get_booking(token_bob, b1["id"])  # cancelled — should show refund

    # Room availability
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
    day_after = (datetime.now(timezone.utc) + timedelta(days=3)).strftime("%Y-%m-%d")
    room_availability(token_alice, room1["id"], tomorrow)
    room_availability(token_alice, room2["id"], day_after)

    # Room stats
    room_stats(token_alice, room1["id"])
    room_stats(token_alice, room2["id"])

    # Usage report (admin only)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    week_later = (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%d")
    usage_report(token_alice, today, week_later)

    # Export CSV (admin only)
    export_csv(token_alice, include_all=True)

    # Cross-org isolation test: Dave trying to see Acme's room
    print("\n\n" + "🔒 MULTI-TENANCY TEST ".ljust(60, "="))
    r = requests.get(f"{BASE}/rooms/{room1['id']}/stats", headers=auth(token_dave))
    pp(f"Dave (Globex) tries Acme room {room1['id']}", r)

    # ============================================================
    #  SUMMARY
    # ============================================================
    print("\n\n" + "📋 CREDENTIALS FOR POSTMAN ".ljust(60, "="))
    print("""
┌─────────────────────────────────────────────────────────────┐
│  Org: Acme Corp                                             │
│  ├── alice (admin)  password: password123                   │
│  ├── bob   (member) password: password123                   │
│  └── carol (member) password: password123                   │
│  Rooms: Focus Room ($10/hr), Conference Hall ($25/hr)       │
│                                                             │
│  Org: Globex Inc                                            │
│  ├── dave  (admin)  password: password123                   │
│  ├── eve   (member) password: password123                   │
│  └── frank (member) password: password123                   │
│  Rooms: War Room ($15/hr), Phone Booth ($5/hr)              │
└─────────────────────────────────────────────────────────────┘

Login endpoint: POST {base}/auth/login
Body: {{"org_name": "Acme Corp", "username": "alice", "password": "password123"}}

Use the access_token in header:
  Authorization: Bearer <access_token>
""".format(base=BASE))
