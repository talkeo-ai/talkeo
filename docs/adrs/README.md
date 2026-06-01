# Architecture Decision Records

This directory captures significant architectural decisions for the Talkeo backend. Each ADR follows a standard format: **Context** (why this came up), **Decision** (what we chose), **Consequences** (what it implies), and **Alternatives** (what else we considered).

ADRs are immutable — when a decision is superseded, a new ADR replaces it rather than editing the old one.

## Index

| # | Title | Status |
|---|---|---|
| [001](./001-layered-architecture.md) | Layered architecture (Clean / Hexagonal) | Accepted |
| [002](./002-provider-ports-adapters.md) | Provider abstraction via ports & adapters | Accepted |
| [003](./003-prompts-as-data.md) | Prompts as data, separated from code | Accepted |
| [004](./004-postgres-schemas-per-context.md) | Postgres schemas per bounded context | Accepted |
| [005](./005-strangler-fig-migration.md) | Strangler Fig migration from internal deprecated codebase | Accepted |
| [006](./006-db-design-principles.md) | Database design principles | Accepted |
| [007](./007-testing-strategy-pr-conventions.md) | Testing strategy and PR conventions | Accepted |
| [008](./008-llm-gateway-and-speech-engines.md) | LLM gateway (LiteLLM) and speech engines (LiveKit) behind provider ports | Accepted |
