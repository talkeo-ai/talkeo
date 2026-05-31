import asyncio
import json
from collections.abc import AsyncIterator

from app.api.sse import StreamError, format_sse, sse_stream


def _collect(source: AsyncIterator[str]) -> list[str]:
    async def run() -> list[str]:
        return [frame async for frame in sse_stream(source)]

    return asyncio.run(run())


async def _gen(items: list[str]) -> AsyncIterator[str]:
    for item in items:
        yield item


async def _raises_stream_error() -> AsyncIterator[str]:
    yield "partial"
    raise StreamError("rate_limit", "slow down")


async def _raises_generic() -> AsyncIterator[str]:
    yield "partial"
    raise RuntimeError("db exploded")


def test_format_sse_single_line():
    assert format_sse("hi") == "data: hi\n\n"


def test_format_sse_with_event():
    assert format_sse("[DONE]", event="done") == "event: done\ndata: [DONE]\n\n"


def test_format_sse_multiline():
    assert format_sse("a\nb") == "data: a\ndata: b\n\n"


def test_sse_stream_appends_done():
    frames = _collect(_gen(["a", "b"]))
    assert frames[:-1] == ["data: a\n\n", "data: b\n\n"]
    assert frames[-1] == "event: done\ndata: [DONE]\n\n"


def test_sse_stream_emits_error_event_and_no_done():
    frames = _collect(_raises_stream_error())
    assert frames[0] == "data: partial\n\n"
    assert frames[-1].startswith("event: error\n")
    assert "[DONE]" not in "".join(frames)

    payload = json.loads(frames[-1].split("data: ", 1)[1].strip())
    assert payload == {"code": "rate_limit", "message": "slow down"}


def test_sse_stream_masks_unhandled_exception():
    frames = _collect(_raises_generic())
    assert frames[-1].startswith("event: error\n")

    payload = json.loads(frames[-1].split("data: ", 1)[1].strip())
    assert payload == {"code": "internal_error", "message": "stream failed"}
    # The raw exception detail must never reach the client.
    assert "db exploded" not in "".join(frames)
