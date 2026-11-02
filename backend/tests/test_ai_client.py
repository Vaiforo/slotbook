import asyncio
import json
from datetime import UTC, datetime

import httpx
import pytest

from app.ai.client import HTTPModelClient, LLMUnavailable
from app.core.config import Settings


def settings():
    return Settings(
        _env_file=None,
        ai_model="test-model",
        ai_api_key="private-test-key",
        redis_url="redis://127.0.0.1:1/0",
        ai_timeout_seconds=1,
    )


@pytest.mark.asyncio
async def test_structured_request_contains_only_time_context_and_bounded_text():
    async def respond(request):
        payload = json.loads(request.content)
        assert payload["response_format"]["json_schema"]["strict"] is True
        assert payload["response_format"]["json_schema"]["schema"]["additionalProperties"] is False
        assert payload["max_completion_tokens"] == 500 and payload["store"] is False
        assert "tools" not in payload
        context = json.loads(payload["messages"][1]["content"])
        assert context == {
            "current_local": "2026-11-02T23:00:00+00:00",
            "timezone": "UTC",
            "text": "tomorrow",
        }
        return httpx.Response(
            200, json={"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}]}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        assert (
            await HTTPModelClient(http, settings()).extract(
                "tomorrow", datetime(2026, 11, 2, 23, tzinfo=UTC), "UTC"
            )
            == "{}"
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fault",
    [
        "429",
        "500",
        "timeout",
        "invalid_json",
        "tool",
        "refusal",
        "truncated",
        "large",
        "redirect",
        "null_message",
    ],
)
async def test_provider_failures_are_bounded_and_never_retried(fault):
    calls = 0

    async def respond(request):
        nonlocal calls
        calls += 1
        if fault == "timeout":
            await asyncio.sleep(2)
        if fault in {"429", "500", "redirect"}:
            return httpx.Response(
                302 if fault == "redirect" else int(fault),
                headers={"Location": "https://other.invalid"},
            )
        if fault == "invalid_json":
            return httpx.Response(200, text="not-json PRIVATE")
        if fault == "large":
            return httpx.Response(200, content=b"a" * 65537)
        if fault == "null_message":
            return httpx.Response(
                200, json={"choices": [{"finish_reason": "stop", "message": None}]}
            )
        message = {"content": "{}"}
        if fault == "tool":
            message["tool_calls"] = [{"name": "create_booking"}]
        if fault == "refusal":
            message["refusal"] = "PRIVATE"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "length" if fault == "truncated" else "stop",
                        "message": message,
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        with pytest.raises(LLMUnavailable):
            await HTTPModelClient(http, settings()).extract("test", datetime.now(UTC), "UTC")
    assert calls == 1


def test_partial_or_insecure_configuration_is_rejected():
    for change in [
        dict(ai_model=None),
        dict(ai_api_key=None),
        dict(ai_url="http://unsafe.invalid"),
        dict(redis_url=None),
    ]:
        values = settings().model_dump() | change
        with pytest.raises(ValueError):
            Settings(_env_file=None, **values)
