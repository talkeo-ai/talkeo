# ADR-007: Testing strategy and PR conventions

**Status:** Accepted
**Date:** 2026-05-27

## Context

A common anti-pattern in early-stage projects is the "vertical-slice PR" that touches the database, the API, the providers, and the frontend all at once "so I can see something working end-to-end". These PRs are:

- Hard to review (too much surface in one place)
- Hard to test (each layer's failures get tangled)
- Hard to revert (the diff spans unrelated concerns)

The layered architecture in [ADR-001](./001-layered-architecture.md) makes single-layer PRs possible. This ADR makes them the convention.

## Decision

### Testing pyramid

```
                ┌──────────────┐
                │  E2E (~5)    │   Few, scheduled. Mac → backend → DB real.
                └──────────────┘
            ┌────────────────────┐
            │ Integration (~20)  │   FastAPI TestClient + testcontainers Postgres.
            └────────────────────┘
        ┌────────────────────────────┐
        │   Unit tests (200+)        │   Domain + use cases with fakes.
        └────────────────────────────┘
```

### Tests per layer

| Layer | Test type | Runs without |
|---|---|---|
| Domain | pure unit | nothing external |
| Application | unit with fakes for ports | DB, real providers |
| Repositories | integration with testcontainers Postgres | API, application |
| Provider adapters | integration with sandbox keys or recorded cassettes | DB, application |
| API routers | endpoint tests with mocked use cases | DB, providers |
| E2E | post-deploy against staging environment | mocks |

### PR conventions

1. **One PR, one layer.** Schema, repository, use case, endpoint, adapter — each gets its own PR.
2. **PR size under approximately 400 lines.** Larger PRs do not get good reviews.
3. **Tests live in the same PR as the code they cover.** No "tests in a follow-up".
4. **CI must be green before merge.** No exceptions.
5. **Conventional commits.** `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`. Enables automated changelogs and semantic versioning.
6. **Squash on merge.** Main branch history is one commit per merged feature.

## Consequences

**Positive:**

- Reviews are focused and arrive quickly.
- Failures are isolated — a failing test points to a specific layer.
- Reverting a problematic change is a single revert.
- New contributors see a clear pattern to follow.

**Negative:**

- A complete feature can require several sequenced PRs.
- The first PR in a sequence sometimes lacks visible end-user value (it's "just the repository"), which can feel slow.

## Alternatives considered

**Vertical-slice PRs.** Optimizes for visible progress per PR but creates the review and revert problems described above. Rejected.

**Trunk-based development with no PR size limits.** Common in some high-throughput teams but requires very strong CI and observability before it pays off. Revisit later if appropriate.
