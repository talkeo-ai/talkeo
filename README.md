# talkeo

Backend API for the Talkeo ecosystem — provider-agnostic LLM, STT, and TTS endpoints, plus a voice-session pipeline powering Talkeo's Mac and Windows apps.

## Highlights

- **Provider-agnostic.** Pick your own LLM (Groq, Anthropic, Gemini, ...), STT (Deepgram, Groq, ElevenLabs), and TTS provider via configuration.
- **Streaming-first.** Server-Sent Events end-to-end. Designed for real-time voice and text experiences.
- **Clean architecture.** Layered (API → Application → Domain → Infrastructure) with strict dependency rules. See [`docs/architecture.md`](./docs/architecture.md).
- **Open source, public roadmap.** The full development plan is in the [org ROADMAP](https://github.com/talkeo-ai/.github/blob/main/profile/ROADMAP.md).

## Two ways to use Talkeo

- **Self-hosted.** Clone the repo, supply your own provider API keys, run locally or deploy to your own infrastructure.
- **Managed Talkeo Cloud.** Zero-config — we host the backend and route to providers internally.

## Quickstart (self-hosted)

```bash
git clone https://github.com/talkeo-ai/talkeo.git
cd talkeo
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# Edit .env with your provider keys
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`. OpenAPI docs at `/docs`.

## Streaming (SSE)

Talkeo streams incremental output (LLM tokens, transforms) over **Server-Sent Events**. `/api/v1/stream/hello` is the reference endpoint that exercises the transport without any provider:

```bash
curl -N http://localhost:8000/api/v1/stream/hello
```

`-N` disables curl's buffering, so you see each word arrive on its own line over ~1.5s rather than all at once — proof the response streams incrementally.

Every Talkeo stream speaks the same three-event contract, so one client parser handles all of them:

```
data: Hello                       ← content chunk (default event)
data: from
...
event: done
data: [DONE]                      ← clean end-of-stream

event: error
data: {"code": "...", "message": "..."}   ← mid-stream failure
```

A `done` event always closes a successful stream; an `error` event (with a machine-readable `code` and a client-safe `message`) signals failure. The client never infers the outcome from connection close. Full spec: [`docs/architecture.md`](./docs/architecture.md#streaming-contract).

Minimal Swift consumer (the pattern the Mac app uses):

```swift
let (bytes, _) = try await URLSession.shared.bytes(from: url)
for try await line in bytes.lines {
    if line.hasPrefix("event: error") { /* read next data: line, surface error */ }
    else if line == "data: [DONE]"   { break }                 // clean end
    else if line.hasPrefix("data: ") { append(String(line.dropFirst(6))) }
}
```

## Repository layout

```
app/
├── api/              # FastAPI routers (HTTP/WS interface)
├── core/             # Configuration, logging, errors
├── domain/           # Entities, value objects, ports
├── application/      # Use cases / orchestrators
└── infrastructure/   # Provider adapters, repositories, cache
prompts/              # Prompt templates (markdown)
migrations/           # Alembic migrations
tests/
docs/
├── architecture.md   # Technical architecture
└── adrs/             # Architecture Decision Records
```

See [`docs/architecture.md`](./docs/architecture.md) for the full architectural overview.

## Documentation

- [Architecture overview](./docs/architecture.md)
- [Architecture Decision Records](./docs/adrs/)
- [Contributing guide](./CONTRIBUTING.md)
- [Org ROADMAP](https://github.com/talkeo-ai/.github/blob/main/profile/ROADMAP.md)

## License

MIT. See [LICENSE](./LICENSE).
