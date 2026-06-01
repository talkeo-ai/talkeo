# ADR-002: Provider abstraction via ports & adapters

**Status:** Accepted
**Date:** 2026-05-27

## Context

Talkeo integrates external providers for LLM, STT, and TTS. Provider choice is contextual:

- **Self-hosted users** pick their own provider and supply their own API keys.
- **Managed Talkeo Cloud** routes to providers internally based on cost, latency, and quality signals.
- **Tests** must run without hitting paid APIs.

Hard-coding any specific provider into application or domain code would lock us into that choice and would expose internal routing in the public repo. The domain must stay provider-agnostic: which provider/model is used is configuration, never code.

## Decision

Define provider **ports** (interfaces, expressed as Python `Protocol`s) in the domain layer:

```python
# domain/providers/llm.py
class LLMProvider(Protocol):
    async def stream_chat(self, messages, **opts) -> AsyncIterator[str]: ...
```

Implement provider **adapters** in the infrastructure layer. Adapters **delegate to a battle-tested engine** rather than hand-rolling each provider's SDK — the LLM adapter delegates to a unified LLM gateway, speech adapters to a voice framework's provider plugins (see **ADR-008** for engine choices and rationale):

```python
# infrastructure/providers/llm/gateway.py
class GatewayLLMProvider:
    """Adapter fulfilling the LLMProvider port by delegating to the LLM gateway.
    The engine handles per-provider differences (reasoning, streaming, tools)."""
    async def stream_chat(self, messages, **opts): ...
```

A **registry** selects the active adapter at startup, based on configuration:

```python
def get_llm_provider(settings: Settings) -> LLMProvider:
    name = settings.LLM_PROVIDER  # provider/model selected by config, not code
    ...
```

Use cases depend only on the port. They never import a specific adapter, and never name a provider.

## Consequences

**Positive:**

- Swapping providers is a one-line config change. No business logic touched.
- Tests inject `FakeLLMProvider` (or similar) and run with no external dependencies.
- The public repo contains only adapters for publicly available providers. Internal routing adapters (if any) load dynamically only when configured.
- Adding a new provider is a single new file in `infrastructure/providers/llm/` plus a registry entry.

**Negative:**

- More files per feature than a "just call the SDK directly" approach.
- The Port-Adapter pattern has a small learning curve for contributors new to Hexagonal architecture.

## Alternatives considered

**Direct SDK calls inside use cases.** Simpler initially. Locks each feature to a specific provider. Untestable without paid API calls. Rejected.

**Single LLM client wrapper class.** Abstracts the SDK but does not enforce the port-adapter discipline. Tends to leak provider-specific options. Rejected.

**Service-locator pattern (global registry).** Hidden dependencies, harder to test, harder to follow data flow. Rejected in favor of explicit dependency injection via FastAPI `Depends`.
