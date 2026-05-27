# ADR-006: Database design principles

**Status:** Accepted
**Date:** 2026-05-27

## Context

Schema mistakes are expensive to fix once production data exists. Indexes added under load cause downtime. Missing foreign keys create orphan data. Inconsistent naming compounds confusion. The predecessor codebase suffered from several of these issues, and the migration is an opportunity to do this right.

We need an explicit, agreed-upon set of database design rules.

## Decision

Adopt the following principles as non-negotiable for all schema work:

1. **Design first, code after.** A schema diagram is reviewed by the team before the first Alembic migration is written.
2. **Indexes from the design.** Every critical query path has its supporting index defined in the same migration that creates the table. `EXPLAIN ANALYZE` is run before any "this is fast" claim.
3. **Foreign keys always.** Referential integrity lives in the database. Application code should not be the only line of defense against orphan rows.
4. **Timestamps on every table.** `created_at` and `updated_at` columns with default `NOW()`. No exceptions.
5. **Soft vs hard delete decided per entity.** `users`: soft delete (audit trail). Session detail tables: hard delete (cleanup). The choice is documented in the migration that creates the table.
6. **JSONB with discipline.** Reserved for genuinely flexible data (user memory facts, free-form settings). Dangerous for fields you will later want to query or index — use proper columns when in doubt.
7. **Naming convention enforced.** Tables plural (`users`, `conversations`). Columns `snake_case`. Primary keys `id`. Foreign keys `<table>_id` (e.g. `user_id`, `conversation_id`).
8. **Reversible migrations.** Both `upgrade()` and `downgrade()` work. Verified in CI by running upgrade-then-downgrade on each migration.
9. **Partitioning planned upfront** for tables expected to exceed millions of rows (turns, events, logs). Not retrofitted under load.
10. **Schemas separate bounded contexts.** See [ADR-004](./004-postgres-schemas-per-context.md).

## Consequences

**Positive:**

- Reduced incidence of schema-related production incidents.
- New tables follow a predictable shape; reviews focus on substance rather than style.
- Migrations are safe to roll back when something goes wrong.

**Negative:**

- More upfront design effort per feature.
- Discipline required to enforce rules even when "just one quick column" is tempting.

## Alternatives considered

**No formal principles — design ad-hoc per feature.** This is how the predecessor got into trouble. Rejected.

**ORM-driven design (let SQLAlchemy auto-generate everything).** Convenient but produces schemas optimized for ORM convenience, not query performance. Indexes and constraints often missed. Rejected as the primary approach — Alembic with hand-tuned migrations remains the source of truth.
