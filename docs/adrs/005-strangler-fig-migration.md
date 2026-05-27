# ADR-005: Strangler Fig migration from internal deprecated codebase

**Status:** Accepted
**Date:** 2026-05-27

## Context

The Talkeo backend has a predecessor: an internal, now-deprecated codebase that handles voice sessions with a working but tightly coupled architecture. It has years of accumulated capabilities (voice pipeline, multi-provider STT/LLM/TTS, prompt assembly, post-session reasoning).

We need to evolve this into the public, clean-architecture backend described in [ADR-001](./001-layered-architecture.md) without:

- Big-bang rewrite (high risk, no incremental value, hard to validate)
- Direct refactor in place (the structural coupling resists incremental improvement)
- Losing users during the transition

## Decision

Apply the **Strangler Fig** migration pattern:

1. **Phase A:** build the new public backend in parallel, addressing greenfield use cases first (stateless LLM/STT/TTS endpoints powering Mac features). The deprecated backend continues running unchanged.

2. **Phase B.1:** rewrite the voice session pipeline in the new architecture. Migrate persistent data (users, conversations, learning state) from the predecessor's storage to the new PostgreSQL schema. The new backend takes over voice sessions. The deprecated backend is decommissioned except for any remaining responsibilities (e.g. auth, deferred to a separate decision).

3. **Phase B.2 and beyond:** add new capabilities only in the new backend.

Each functional area is migrated as a separate feature, not as a bulk port. Issues track migration work explicitly and reference the capability (not the deprecated repo's code) so external contributors can pick them up.

## Consequences

**Positive:**

- Each migration step is small, reviewable, and reversible.
- Users see no disruption — they use the new endpoints as they come online.
- The team learns the new architecture by building greenfield features (Phase A) before tackling the migration (Phase B.1).
- Public issues describe **what** to build, not **what to port from where**. External contributors can take them without access to internal repositories.

**Negative:**

- Two backends run in parallel during the transition, doubling operational surface temporarily.
- Disciplined decommissioning required to avoid the deprecated code lingering indefinitely.

## Alternatives considered

**Big-bang rewrite.** Higher risk, no users-visible value during the rewrite, hard to validate behavior parity. Rejected.

**In-place refactor of the deprecated codebase.** The coupling is structural; refactoring inside it would compromise the clean-architecture goal. Rejected.

**Maintain both indefinitely.** Operational and cognitive cost grows over time. Each new feature would face the "which backend?" decision. Rejected — deprecation is part of the plan.
