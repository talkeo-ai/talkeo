import asyncio
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.api.sse import sse_response

router = APIRouter(prefix="/stream", tags=["stream"])

_HELLO_MESSAGE = "Hello from the Talkeo streaming base endpoint."


async def _hello_chunks() -> AsyncIterator[str]:
    """Demo source: yield one word at a time with a small delay so `curl -N`
    shows chunks arriving incrementally rather than all at once."""
    for word in _HELLO_MESSAGE.split():
        yield word + " "
        await asyncio.sleep(0.2)


@router.get("/hello")
async def stream_hello() -> StreamingResponse:
    return sse_response(_hello_chunks())
