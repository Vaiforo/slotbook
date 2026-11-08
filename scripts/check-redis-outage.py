"""Run against the disposable production stack while Redis is stopped."""

import json
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

base = sys.argv[1]
for path in ["/api/v1/auth/login", "/api/v1/bookings"]:
    try:
        urlopen(
            Request(base + path, data=b"{}", headers={"Content-Type": "application/json"}),
            timeout=5,
        )
    except HTTPError as response:
        assert response.code == 503
        assert json.load(response)["error"]["code"] == "rate_limit_unavailable"
        assert response.headers["Retry-After"] == "5"
    else:
        raise AssertionError("Write admitted without Redis")
for path in ["/health/ready", "/api/v1/specialists/anna-belova"]:
    assert urlopen(base + path, timeout=5).status == 200
print("Redis outage blocks writes and preserves reads")
