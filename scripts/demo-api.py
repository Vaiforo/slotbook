"""Local synthetic booking journey; never prints the management credential."""

import argparse
import json
from datetime import UTC, datetime, timedelta
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", default="http://127.0.0.1:8000")
parser.add_argument(
    "--book-and-cancel",
    action="store_true",
    required=True,
    help="Explicitly create and cancel a synthetic booking in the demo database",
)
args = parser.parse_args()
base = args.base_url.rstrip("/")
url = urlsplit(base)
if url.scheme not in {"http", "https"} or url.hostname not in {"localhost", "127.0.0.1", "::1"}:
    parser.error("Use a loopback URL and a local demo database")
if url.username or url.password or url.path or url.query or url.fragment:
    parser.error("Use an origin without credentials, path, query or fragment")


def request(path, method="GET", data=None, token=None):
    headers = {"Accept": "application/json"}
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
            return json.load(response)
    except HTTPError as exc:
        raise SystemExit(f"Demo stopped: HTTP {exc.code}; mutations are not retried") from None


profile = request("/api/v1/specialists/demo")
now = datetime.now(UTC)
query = urlencode({"from": now.isoformat(), "to": (now + timedelta(days=7)).isoformat()})
path = f"/api/v1/specialists/demo/slots?{query}"
slots = request(path)["items"]
if not slots:
    raise SystemExit("No free demo slots: run make seed in the local demo database")
slot_id = slots[0]["id"]
created = request(
    "/api/v1/bookings",
    "POST",
    {
        "slot_id": slot_id,
        "client_name": "Демо-клиент",
        "client_email": "demo-client@example.com",
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
print(f"Demo passed: {profile['slug']} → booking → private read → cancellation → free slot")
