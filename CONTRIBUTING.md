# Contributing to Talkeo

Thank you for considering a contribution. This guide covers the basics.

## Before you start

- Read [`docs/architecture.md`](./docs/architecture.md) to understand how the codebase is structured.
- Skim the [ADRs](./docs/adrs/) for the reasoning behind major decisions.
- Browse open issues. Issues labeled `good first issue` are scoped entry points.

## Development setup

Requirements:
- Python 3.12+
- Docker (for local Postgres in Phase B.1+)
- Provider API keys for the components you want to exercise (Groq for LLM, ElevenLabs for TTS, etc.)

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

## Architecture rules (enforced in review)

When opening a PR, the reviewer will check that your code respects:

1. **Layered dependencies.** Outer layers depend on inner layers, never the reverse.
2. **No business logic in routers.** Routers parse, call use cases, format responses.
3. **No database calls in domain.** Domain code does not import any storage SDK.
4. **Providers behind ports.** Every external service has a `Protocol` in `domain/` and an adapter in `infrastructure/`.
5. **Prompts are data.** No hardcoded prompt strings in Python — load from `prompts/*.md`.

See [`docs/architecture.md`](./docs/architecture.md#inviolable-rules) for the full list.

## Adding a new provider adapter

1. Confirm the port exists in `app/domain/providers/`.
2. Create your adapter under `app/infrastructure/providers/<kind>/<provider>.py`. Implement the port.
3. Register the adapter in `app/infrastructure/providers/<kind>/registry.py`.
4. Add an integration test in `tests/integration/providers/`. Use a sandbox key from CI secrets or VCR cassettes for recorded responses.
5. Document any new environment variables in `.env.example` and the README.

## Pull request conventions

- **One PR, one layer.** Schema, repository, use case, endpoint, adapter — each in its own PR.
- **PR size under ~400 lines** of meaningful diff.
- **Tests in the same PR as the code.** No "tests in a follow-up".
- **CI must be green before merge.**
- **Conventional commits**: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`.
- **Squash on merge.**

See [ADR-007](./docs/adrs/007-testing-strategy-pr-conventions.md) for the rationale.

## Proof of work (required for review)

AI-generated code is welcome (see the project mindset), but **AI output alone is never enough** — you must run it and confirm it works *before* requesting review. A PR that "should work" but was never executed will be closed. Every PR must include:

- **Evidence it ran.** Paste the `pytest` output for the tests you added, plus a real run of the behavior — a `curl`/`httpie` transcript against a local server for an endpoint, or a **short terminal recording / GIF** for anything with visible streaming or runtime behavior (e.g. an SSE or audio stream).
- **It builds and tests pass locally** — `uv run pytest tests/` green, not just CI.
- **What you actually tested** — the real steps you ran, not aspirational checkboxes.

## Testing

```bash
pytest tests/unit          # fast, no externals
pytest tests/integration   # requires Docker (testcontainers)
pytest tests/e2e           # against a deployed environment, scheduled
```

Aim for the [testing pyramid](./docs/architecture.md#testing-strategy): many unit tests, a moderate set of integration tests, a small set of end-to-end tests.

## Reporting issues

For bugs, include:
- Steps to reproduce
- Expected vs actual behavior
- Environment (OS, Python version, provider in use)
- Logs if relevant

For feature requests, describe the use case before proposing an implementation. Discussion via an issue is preferred over a surprise PR for non-trivial work.

## License

By contributing you agree your contributions are licensed under the same [MIT license](./LICENSE) as the project.
