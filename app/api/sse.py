"""Server-Sent Events (SSE) transport — the base for every streaming endpoint.

A streaming endpoint produces an ``AsyncIterator[str]`` of content chunks
(today a demo generator; tomorrow ``LLMProvider.stream_chat``). The helpers
here frame each chunk as an SSE message, append a terminal ``done``/``error``
event, and wrap the whole thing in a ``StreamingResponse`` with the headers
proxies need to flush incrementally.

Wire contract (versioned with the API; parsed by the Mac/Windows clients):

    data: <chunk>\\n\\n                              # content (default event)
    event: done\\n
    data: [DONE]\\n\\n                               # clean end-of-stream
    event: error\\n
    data: {"code": "...", "message": "..."}\\n\\n     # mid-stream failure

The ``error`` event exists from day one so clients can tell "stream finished"
apart from "stream broke" — connection close alone is ambiguous.
"""

import json
from collections.abc import AsyncIterator

import structlog
from fastapi.responses import StreamingResponse

log = structlog.get_logger(__name__)

DONE_SENTINEL = "[DONE]"

# Headers that keep SSE flushing chunk-by-chunk instead of buffering.
SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    # Disable proxy buffering (e.g. nginx) so chunks reach the client immediately.
    "X-Accel-Buffering": "no",
}


class StreamError(Exception):
    """Raised by a stream source to emit a clean ``event: error`` frame.

    ``code`` is a stable, machine-readable token the client switches on;
    ``message`` is a human-readable, client-safe description (no internals).
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def format_sse(data: str, *, event: str | None = None) -> str:
    """Frame a payload as a single SSE message.

    Multi-line payloads are split across repeated ``data:`` lines so the
    message stays spec-valid. Omit ``event`` for the default (content) event.
    """
    framed = ""
    if event is not None:
        framed += f"event: {event}\n"
    for line in data.split("\n"):
        framed += f"data: {line}\n"
    return framed + "\n"


async def sse_stream(source: AsyncIterator[str]) -> AsyncIterator[str]:
    """Frame a content stream and append the terminal ``done``/``error`` event."""
    try:
        async for chunk in source:
            yield format_sse(chunk)
    except StreamError as exc:
        log.warning("sse_stream.error", code=exc.code, message=exc.message)
        yield format_sse(
            json.dumps({"code": exc.code, "message": exc.message}),
            event="error",
        )
        return
    except Exception:
        # Never leak internals to the client — log the detail, send a generic frame.
        log.exception("sse_stream.unhandled")
        yield format_sse(
            json.dumps({"code": "internal_error", "message": "stream failed"}),
            event="error",
        )
        return
    yield format_sse(DONE_SENTINEL, event="done")


def sse_response(source: AsyncIterator[str]) -> StreamingResponse:
    """Wrap a content stream in an SSE ``StreamingResponse``."""
    return StreamingResponse(
        sse_stream(source),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
