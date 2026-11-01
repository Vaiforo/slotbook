import random
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx


class DeliveryError(Exception):
    def __init__(self, code: str, retryable: bool, delay: int = 0):
        self.code, self.retryable, self.delay = code, retryable, delay


def retry_delay(value: str | None) -> int:
    try:
        seconds = int(value or "0")
    except ValueError:
        try:
            seconds = int(
                (
                    parsedate_to_datetime(value or "").astimezone(UTC) - datetime.now(UTC)
                ).total_seconds()
            )
        except ValueError, TypeError, OverflowError:
            seconds = 0
    return max(0, min(86400, seconds))


def backoff(attempt: int, minimum: int) -> int:
    return int(max(minimum, min(3600, 2 ** min(attempt, 12)) + random.randint(0, 5)))


def send(
    client: httpx.Client,
    url: str | None,
    api_key: str | None,
    event_id: str,
    recipient: str,
    subject: str,
    message: str,
) -> None:
    if not url:
        raise DeliveryError("provider_not_configured", True)
    headers = {"Idempotency-Key": event_id}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    try:
        response = client.post(
            url, headers=headers, json={"to": recipient, "subject": subject, "text": message}
        )
    except httpx.HTTPError:
        raise DeliveryError("provider_network", True) from None
    if 200 <= response.status_code < 300:
        return
    retryable = response.status_code == 429 or 500 <= response.status_code < 600
    raise DeliveryError(
        f"provider_http_{response.status_code}",
        retryable,
        retry_delay(response.headers.get("Retry-After")),
    )
