"""Local synthetic booking journey; never prints the management credential."""

import argparse
import json
import os
import secrets
from datetime import UTC, datetime, timedelta
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", default="http://127.0.0.1:8000")
parser.add_argument(
    "--book-and-cancel",
    action="store_true",
    required=True,
    help="Explicitly create and cancel a synthetic booking in the synthetic local database",
)
args = parser.parse_args()
base = args.base_url.rstrip("/")
url = urlsplit(base)
if url.scheme not in {"http", "https"} or url.hostname not in {
    "localhost",
    "127.0.0.1",
    "::1",
}:
    parser.error("Use a loopback URL and a local synthetic database")
if url.username or url.password or url.path or url.query or url.fragment:
    parser.error("Use an origin without credentials, path, query or fragment")


cookie = ""
csrf = ""
origin = os.getenv("SLOTBOOK_PUBLIC_ORIGIN", "http://127.0.0.1:5173")


def request(path, method="GET", data=None, token=None):
    global cookie
    headers = {"Accept": "application/json", "Origin": origin}
    if cookie:
        headers["Cookie"] = cookie
    if csrf:
        headers["X-CSRF-Token"] = csrf
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = Request(
        base + path,
        method=method,
        headers=headers,
        data=json.dumps(data).encode() if data is not None else None,
    )
    try:
        with urlopen(req, timeout=15) as response:
            if response.headers.get("Set-Cookie"):
                cookie = response.headers["Set-Cookie"].split(";", 1)[0]
            return json.load(response)
    except HTTPError as exc:
        raise SystemExit(
            f"Scenario stopped: HTTP {exc.code}; mutations are not retried"
        ) from None


identity = request(
    "/api/v1/auth/register",
    "POST",
    {
        "role": "client",
        "full_name": "Synthetic client",
        "email": f"scenario-{uuid4().hex}@example.com",
        "password": secrets.token_urlsafe(24),
        "timezone": "UTC",
    },
)
csrf = identity["csrf_token"]
profile = request("/api/v1/specialists/anna-belova")
now = datetime.now(UTC)
query = urlencode(
    {"from": now.isoformat(), "to": (now + timedelta(days=7)).isoformat()}
)
path = f"/api/v1/specialists/anna-belova/slots?{query}"
slots = request(path)["items"]
if not slots:
    raise SystemExit(
        "No free slots: run make seed-specialists in the local synthetic database"
    )
slot_id = slots[0]["id"]
created = request(
    "/api/v1/bookings",
    "POST",
    {
        "slot_id": slot_id,
        "client_name": "Synthetic client",
        "client_email": identity["email"],
    },
)
booking_path = f"/api/v1/bookings/{created['id']}"
token = created["manage_token"]
try:
    assert created["status"] == "confirmed"
    assert all(s["id"] != slot_id for s in request(path)["items"])
    assert request(booking_path, token=token)["id"] == created["id"]
finally:
    cancelled = request(booking_path + "/cancel", "POST", token=token)
assert cancelled["status"] == "cancelled"
assert any(s["id"] == slot_id for s in request(path)["items"])
print(
    f"Scenario passed: {profile['slug']} → booking → private read → cancellation → free slot"
)
