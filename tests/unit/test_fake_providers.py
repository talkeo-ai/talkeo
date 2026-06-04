import asyncio

from app.domain.providers.messages import Message
from app.domain.providers.stt import Transcript
from app.infrastructure.providers.llm.fake import FakeLLMProvider
from app.infrastructure.providers.stt.fake import FakeSTTProvider
from app.infrastructure.providers.tts.fake import FakeTTSProvider


def test_fake_llm_streams_text_deltas():
    async def run() -> list[str]:
        provider = FakeLLMProvider()
        messages = [Message(role="user", content="hola")]
        return [delta async for delta in provider.stream_chat(messages)]

    deltas = asyncio.run(run())

    assert all(isinstance(d, str) for d in deltas)
    assert "".join(deltas).strip() == "fake reply to: hola"


def test_fake_tts_streams_audio_bytes():
    async def run() -> list[bytes]:
        provider = FakeTTSProvider()
        return [chunk async for chunk in provider.synthesize("hi")]

    chunks = asyncio.run(run())

    assert len(chunks) == 2
    assert all(isinstance(c, bytes) for c in chunks)
    assert b"".join(chunks) == b"fake audio for: hi"


def test_fake_stt_returns_transcript():
    async def run() -> Transcript:
        provider = FakeSTTProvider()
        return await provider.recognize(b"1234")

    transcript = asyncio.run(run())

    assert isinstance(transcript, Transcript)
    assert "4 bytes" in transcript.text
