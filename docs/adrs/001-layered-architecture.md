# ADR-001: Layered architecture (Clean / Hexagonal)

**Status:** Accepted
**Date:** 2026-05-27

## Context

The Talkeo backend serves multiple clients (Mac, Windows, future Web and Mobile). It integrates several swappable external providers (LLM, STT, TTS, pronunciation), persists session and learning data, and must remain understandable and modifiable by external contributors.

The predecessor codebase (internal, now deprecated) suffered from significant coupling: prompt assembly logic mixed with database queries, business rules embedded in WebSocket handlers, provider-specific code scattered across routes. This made testing, evolution, and contribution all difficult.

We need an architectural shape that resists this drift over time.

## Decision

Adopt a **layered architecture** following the Clean Architecture / Hexagonal pattern:

1. **API layer** (FastAPI routers): thin HTTP/WS handling. Parse requests, call use cases, format responses.
2. **Application layer**: use cases / orchestrators. Coordinate domain operations. Do not know about transport or storage.
3. **Domain layer**: entities, value objects, domain services, and ports (interfaces). Pure business logic. No external dependencies.
4. **Infrastructure layer**: adapters that implement domain ports — providers, repositories, cache, prompt loader.

**Dependency rule:** dependencies point inward. Infrastructure depends on domain. Domain depends on nothing external.

## Consequences

**Positive:**

- Domain logic is testable in pure isolation (no DB, no FastAPI, no providers).
- Provider and storage choices are isolated to one layer. Swapping them does not touch business logic.
- New contributors can start by reading the domain layer alone to understand the system's "what" before its "how".
- Pull requests can target a single layer, keeping reviews focused and small.

**Negative:**

- More indirection than a flat structure. A simple feature touches multiple files.
- Discipline is required: it is tempting to "shortcut" by importing infrastructure into application or domain.
- More upfront design work before the first feature ships.

The team accepts these costs in exchange for long-term maintainability and contributor accessibility.

## Alternatives considered

**Flat structure (single package, no layers).** Faster to start, but the predecessor's pain points (coupling, untestable units, scattered logic) all stem from this approach. Rejected.

**Modular monolith without strict layering.** Looser version of the above. Initially appealing for solo development, but provides no enforcement against drift. Rejected — the structural discipline is the whole point.

**Microservices.** Strong separation, but premature complexity for current scale. Operational overhead would slow development. Will be revisited if specific bounded contexts justify separate deployment.
