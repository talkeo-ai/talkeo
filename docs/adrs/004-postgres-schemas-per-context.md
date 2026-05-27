# ADR-004: Postgres schemas per bounded context

**Status:** Accepted
**Date:** 2026-05-27

## Context

The backend has multiple bounded contexts: **Session** (conversations and turns), **User** (profiles, preferences), **Learning** (can-dos, errors, memory), **Pedagogy** (curriculum, class plans), **Director** (post-session summaries and evaluations), **Pronunciation** (assessments).

Putting all tables in the default `public` schema would:

- Make ownership unclear at a glance (`messages` could belong to any of three contexts).
- Encourage accidental cross-context coupling (a route handler joining across unrelated tables).
- Complicate permission management if we later restrict access per context.

## Decision

Use **PostgreSQL schemas** as the unit of ownership for bounded contexts:

```sql
CREATE SCHEMA session;
CREATE SCHEMA user_data;     -- "user" is reserved in SQL contexts; we use user_data
CREATE SCHEMA learning;
CREATE SCHEMA pedagogy;
CREATE SCHEMA director;
CREATE SCHEMA pronunciation;
```

Each repository in `infrastructure/repositories/postgres/` reads and writes a single schema. Cross-schema queries are technically allowed but discouraged — go through the relevant repository instead.

Naming convention: tables are plural (`conversations`, `turns`, `users`), columns are `snake_case`, primary keys are `id`, foreign keys are `<table>_id`.

## Consequences

**Positive:**

- Visual ownership: `session.conversations` is unambiguously the Session context's.
- Easier permission management later (grant per-schema access).
- Cleaner mental model when discussing the database with new contributors.
- Migrations grouped by context, reducing PR conflicts.

**Negative:**

- Some tooling (ORM model definitions, dashboards) requires explicit schema configuration. Worth the cost.
- One-time effort to set up schema-aware Alembic configuration.

## Alternatives considered

**Single `public` schema with naming-convention prefixes** (`session_conversations`, `learning_can_dos`). Achieves visual grouping but provides no enforcement. Rejected.

**Separate databases per context.** Strongest isolation, but blocks cross-context referential integrity (foreign keys cannot cross databases). Operational overhead unjustified for current scale. Rejected.

**Schema-less / single-table-per-context with JSONB.** Trades structure for flexibility. Loses indexability and constraint enforcement. Rejected for relational entities; JSONB still used selectively for genuinely unstructured data (memory facts, settings).
