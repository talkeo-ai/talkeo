# Talkeo Backend Architecture

> Public technical architecture for the Talkeo backend. See [ROADMAP.md](https://github.com/talkeo-ai/.github/blob/main/profile/ROADMAP.md) for the high-level plan and phases.

## Goals

1. **Multi-client by design.** Mac, Windows, Web, and Mobile consume the same backend. None of them are coupled to backend internals beyond the HTTP/WebSocket contract.
2. **Provider-agnostic.** LLM, STT, and TTS providers are swappable via configuration — the domain never names a provider. Adapters delegate to engines: LLM to a unified gateway, speech to a voice framework's plugins (see [ADR-008](./adrs/008-llm-gateway-and-speech-engines.md)). Self-hosted users plug in their own keys; managed Cloud routes internally.
3. **Clean separation of concerns.** Prompts are not mixed with logic. Database queries are not made from route handlers. Providers do not appear in domain code.
4. **Independent bounded contexts.** Session, Pedagogy, User, Learning, and Director each own their data and rules. They share a database, not logic.
5. **Public-safe.** Any external contributor can read the code without seeing secrets, internal IP, or provider-routing logic.

## Layered architecture (Clean / Hexagonal)

```
┌──────────────────────────────────────────────────────────────┐
│  Clients: Mac, Windows, Web, Mobile                          │
│  Consume HTTP/WS. Know nothing of the backend beyond its     │
│  contract (OpenAPI schema).                                  │
└──────────────────────────────────────────────────────────────┘
                          │ HTTP / WS
                          ▼
┌──────────────────────────────────────────────────────────────┐
│  API Layer (FastAPI routers)                                 │
│  Thin: parse request → call use case → format response.      │
│  Auth middleware, rate limits, input validation.             │
│  No business logic.                                          │
└──────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│  Application Layer (Use Cases / Orchestrators)               │
│  - SessionOrchestrator: voice session state machine.         │
│  - PromptAssembler: composes prompts from data + templates.  │
│  - DirectorPipeline: post-session reasoning.                 │
│  - TransformService: translate/improve stateless flows.      │
│  Orchestrates domain. Does not know providers or storage.    │
└──────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│  Domain Layer (Pure business logic)                          │
│  Entities, value objects, domain services, ports.            │
│  No FastAPI, no SQL, no external SDKs.                       │
│  Fully unit-testable in isolation.                           │
└──────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│  Infrastructure Layer (Adapters)                             │
│  - Provider adapters: LLM → gateway; STT/TTS → voice plugins.│
│  - Repositories: Postgres via asyncpg / SQLAlchemy.          │
│  - Cache: in-memory (Phase A-B), Redis (Phase C+).           │
│  - Prompt loader: reads /prompts/*.md.                       │
│  Implements ports defined in the domain layer.               │
└──────────────────────────────────────────────────────────────┘
```

**Dependency rule:** arrows always point inward. Infrastructure depends on domain. Domain depends on nothing.

## Repository structure

```
talkeo/
├── app/
│   ├── main.py                       # FastAPI app, lifespan, middleware
│   ├── api/                          # HTTP/WS interface (thin)
│   │   ├── deps.py                   # DI definitions
│   │   └── v1/                       # versioned routers
│   ├── core/                         # cross-cutting (config, logging, errors)
│   ├── domain/                       # PURE business logic
│   │   ├── session/
│   │   ├── pedagogy/
│   │   ├── user/
│   │   ├── learning/
│   │   ├── providers/                # provider PORTS (interfaces)
│   │   └── shared/                   # value objects
│   ├── application/                  # USE CASES (orchestrators)
│   └── infrastructure/               # ADAPTERS
│       ├── providers/                # LLM, STT, TTS, pronunciation
│       ├── repositories/             # postgres adapters
│       ├── cache/
│       └── prompts/                  # template loader
├── prompts/                          # markdown templates (not code)
├── migrations/                       # Alembic
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── docs/
│   ├── architecture.md               # this file
│   └── adrs/                         # Architecture Decision Records
├── Dockerfile
├── pyproject.toml
└── README.md
```

## Inviolable rules

1. **Dependency direction:** outer layers depend on inner layers. Never the reverse.
2. **No business logic in routers.** Routers parse requests, call use cases, format responses.
3. **No DB calls in domain.** Domain code does not import SQLAlchemy, asyncpg, or any storage SDK.
4. **Providers behind interfaces.** Every external service has a Port (Protocol/ABC) in domain and an Adapter in infrastructure.
5. **Prompts are data.** Never hardcode prompt strings in Python. Always load from `/prompts/*.md`.
6. **DI everywhere.** Routers and use cases receive dependencies via FastAPI `Depends`. No globals.
7. **Tests by layer.** Domain tests run in isolation. Application tests use fakes for ports. Integration tests for adapters.
8. **One bounded context = one DB schema.** Use Postgres `CREATE SCHEMA` to enforce ownership: `session.*`, `user.*`, `learning.*`.
9. **Config via env, validated with Pydantic.** No secret strings in code.
10. **Observability built-in.** structlog from day one, correlation IDs in requests, metrics and traces with reserved slots.

## Provider abstraction

The contract lives in `domain/providers/`:

```python
# domain/providers/llm.py
from typing import Protocol, AsyncIterator

class LLMProvider(Protocol):
    """Port. Domain depends on this — not on any specific provider."""
    async def stream_chat(
        self,
        messages: list[Message],
        model: str | None = None,
        **opts,
    ) -> AsyncIterator[str]: ...
```

Adapters implement it in `infrastructure/providers/llm/`. Rather than hand-rolling each provider's SDK, the adapter **delegates to a unified LLM gateway** that normalizes providers and their reasoning/streaming controls; speech adapters delegate to a voice framework's provider plugins (which also serve the realtime agent). See [ADR-008](./adrs/008-llm-gateway-and-speech-engines.md) for the engine choices and the latency discipline a gateway requires.

```python
# infrastructure/providers/llm/gateway.py
class GatewayLLMProvider:
    """Fulfills the LLMProvider port by delegating to the LLM gateway.
    The gateway handles per-provider differences; this stays provider-agnostic."""
    async def stream_chat(self, messages, model=None, **opts) -> AsyncIterator[str]:
        ...
```

A factory selects which adapter to load based on configuration:

```python
# infrastructure/providers/llm/registry.py
def get_llm_provider(settings: Settings) -> LLMProvider:
    name = settings.LLM_PROVIDER  # provider/model selected by config, not code
    ...
```

**Self-hosted users** point the gateway at their own provider + key and run. **Managed Talkeo Cloud** routes internally via the gateway — the public code stays clean and never names a provider.

## Streaming contract

Talkeo is streaming-first: LLM tokens, transforms, and any incremental output reach the clients over **Server-Sent Events (SSE)**. The transport is a thin, reusable layer (`app/api/sse.py`) that frames an `AsyncIterator[str]` of content chunks — the same shape every provider port already exposes (`LLMProvider.stream_chat -> AsyncIterator[str]`). Endpoints produce chunks; they never format SSE by hand.

Every stream — `/api/v1/stream/hello` today, LLM and transform endpoints later — speaks one wire contract of three event types:

```
data: <chunk>\n\n                              # content (default event, no `event:` line)
event: done\n
data: [DONE]\n\n                               # clean end-of-stream sentinel
event: error\n
data: {"code": "...", "message": "..."}\n\n     # mid-stream failure
```

Rules:

1. **Content frames carry no `event:` line** — they are the default SSE message. Multi-line chunks are split across repeated `data:` lines (spec requirement).
2. **`done` is mandatory on success.** A stream that ends without `done` is treated as broken by the client. Connection close alone is ambiguous (success vs. dropped socket), so we never rely on it.
3. **`error` reports mid-stream failure.** `code` is a stable machine token the client switches on; `message` is human-readable and **client-safe**. Sources raise `StreamError(code, message)` for expected failures; any other exception is logged server-side and masked as `{"code": "internal_error", "message": "stream failed"}` — internals never reach the client.
4. **`done` and `error` are mutually exclusive** — a stream emits exactly one terminal event.

Defining `error` from the first endpoint (rather than when the LLM lands) keeps the contract — and the client parser — stable across every future stream. This mirrors how OpenAI, Anthropic, and Groq frame their SSE APIs with named events.

## Prompts as data

The legacy backend (now deprecated, internal) had prompt assembly tightly coupled with database calls, transformations, and conditional logic in a single 850+ line module. This is the failure mode we explicitly avoid.

The rewrite separates three concerns:

1. **Templates** live in `/prompts/*.md` as plain markdown with placeholders.
2. **Data assembly** is a use case (`PromptDataAssembler`) that takes a typed `SessionContext` and returns a typed `LeoPromptData`.
3. **Composition** is a use case (`PromptComposer`) that takes data + templates and returns the final string.

```python
class PromptDataAssembler:
    def __init__(self, user_repo: UserRepository, curriculum: CurriculumService, ...):
        ...

    async def assemble_for_session(self, session: Session) -> LeoPromptData:
        return LeoPromptData(
            user=await self.user_repo.get(session.user_id),
            level=...,
            in_progress_can_dos=...,
            ...,
        )

class PromptComposer:
    def __init__(self, prompt_loader: PromptLoader):
        ...

    def compose_leo_prompt(self, data: LeoPromptData) -> str:
        sections = [
            self.loader.get("base/leo_identity.md"),
            self.loader.get(f"levels/{data.level}.md"),
            self.loader.get(f"pairs/{data.pair}/identity.md"),
            self._render_dynamic(data),
        ]
        return "\n\n".join(sections)
```

This makes prompts versionable in git, testable in isolation, and cacheable (the static prefix is immutable per user level + language pair).

## Database design

A single PostgreSQL database with schemas per bounded context:

```sql
CREATE SCHEMA session;        -- conversations, turns, session state
CREATE SCHEMA user;           -- profiles, preferences
CREATE SCHEMA learning;       -- can_dos, errors, memory
CREATE SCHEMA pedagogy;       -- curriculum_units, class_plans
CREATE SCHEMA director;       -- session_summaries, evaluations
```

Each repository in `infrastructure/repositories/postgres/` owns a single schema. Cross-schema queries are technically allowed but discouraged — go through the relevant repository instead.

### DB design principles

1. **Design first, code after.** Schema diagrams reviewed before the first migration.
2. **Indexes from day one.** Every critical query path has its index. `EXPLAIN ANALYZE` runs before claiming "fast".
3. **Foreign keys always.** Referential integrity in the database, not in code.
4. **Timestamps on every table:** `created_at`, `updated_at` with default `NOW()`.
5. **Soft vs hard delete decided per entity** and documented.
6. **JSONB with discipline.** Useful for flexible data (memory, settings). Dangerous for fields you'll later want to query or index.
7. **Naming conventions enforced.** Tables plural (`users`, `conversations`). Columns `snake_case`. Primary keys `id`, foreign keys `<table>_id`.
8. **Reversible migrations.** Both `upgrade()` and `downgrade()` work, tested in CI.
9. **Partitioning planned upfront** for high-volume tables (turns, events).
10. **Schemas separate bounded contexts.** Not alphabetical grouping.

## Testing strategy

```
                ┌────────────────┐
                │   E2E (~5)     │   Few, scheduled. Mac → backend → DB real.
                └────────────────┘
            ┌────────────────────────┐
            │  Integration (~20)     │   FastAPI TestClient + testcontainers.
            └────────────────────────┘
        ┌────────────────────────────────┐
        │      Unit tests (200+)          │   Domain + use cases with fakes.
        └────────────────────────────────┘
```

**Per-layer rules:**

| Layer | Tests | Without |
|---|---|---|
| Domain | pure unit | nothing external |
| Application | unit with fakes for ports | DB, providers |
| Repositories | integration with testcontainers Postgres | API, use cases |
| Provider adapters | integration with sandbox keys or recorded cassettes | DB, app |
| API routers | endpoint tests with mocked use cases | DB, providers |
| E2E | post-deploy against staging | mocks |

## PR conventions

- **One PR, one layer.** Schema, repository, use case, endpoint, adapter — each its own PR.
- **PR size under ~400 lines.** Larger PRs do not get good reviews.
- **Tests in the same PR as the code.** No "tests later".
- **CI green before merge.** No exceptions.
- **Conventional commits:** `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`.
- **Squash on merge.**

## ADRs

Decisions recorded in [`docs/adrs/`](./adrs/):

- ADR-001: Layered architecture (Clean / Hexagonal)
- ADR-002: Provider abstraction via ports & adapters
- ADR-003: Prompts as data
- ADR-004: Postgres schemas per bounded context
- ADR-005: Strangler Fig migration from internal deprecated codebase
- ADR-006: Database design principles
- ADR-007: Testing strategy and PR conventions
- ADR-008: LLM gateway (LiteLLM) and speech engines (LiveKit) behind provider ports

## Contributing

External contributions are welcome. See [`CONTRIBUTING.md`](../CONTRIBUTING.md) for the development setup, testing workflow, and conventions.

Issues labeled `good first issue` are scoped, well-defined, and a good entry point.
