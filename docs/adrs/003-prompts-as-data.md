# ADR-003: Prompts as data, separated from code

**Status:** Accepted
**Date:** 2026-05-27

## Context

The predecessor's `PromptBuilder` module was 850+ lines that mixed:

- File loading (reading markdown templates from disk)
- Database lookups (user profile, curriculum, recent errors)
- Data transformations (formatting timestamps, deriving labels)
- Conditional logic (which sections appear under which states)
- String assembly (composing the final prompt)

This made it impossible to:

- Cache the static portions of the prompt
- Test prompt composition without a live database
- Let an external contributor change a single template wording without reading the full module
- Version prompt evolution in a meaningful way (text changes were buried in code diffs)

## Decision

Split the concern into three independent pieces:

1. **Templates** live in `/prompts/*.md` as plain markdown with placeholders. No code, no logic.
2. **Data assembly** is a use case (`PromptDataAssembler`) that takes a `SessionContext`, consults domain services and repositories, and returns a typed `LeoPromptData` value object.
3. **Composition** is a use case (`PromptComposer`) that takes the data plus the templates and returns the final prompt string. Pure function.

The data assembler depends on ports (`UserRepository`, `CurriculumService`, etc.). The composer depends on a `PromptLoader` port.

## Consequences

**Positive:**

- Templates are versioned in git as plain text. Diffs are readable, even by non-engineers.
- `PromptComposer` is a pure function — easy to unit test with sample data.
- Static portions of the prompt are loaded once at startup and cached in memory.
- A clear boundary marker (`__STATIC_PREFIX__` / `__DYNAMIC_PREFIX__`) enables provider-level prompt caching (Anthropic, etc.) for the immutable portion.
- External contributors can propose template improvements without touching Python code.

**Negative:**

- Two extra abstractions to navigate (assembler + composer) instead of one monolithic builder.
- Requires discipline: any new dynamic section must be added as a field in `LeoPromptData`, not inlined into the composer.

## Alternatives considered

**Refactor the existing `PromptBuilder` in place.** Considered but rejected — the coupling is structural, not cosmetic. A refactor without separation would leak.

**Templating engine (Jinja2, etc.).** Possible, but prompts are simple enough that string composition with placeholders is clearer than introducing a templating dependency. Revisit if templates grow conditional logic.

**Prompts loaded from a database (configurable per-tenant).** Premature for current scale. Filesystem + git versioning is sufficient until multi-tenant prompt customization becomes a real requirement.
