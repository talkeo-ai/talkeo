# ADR-008: LLM gateway (LiteLLM) and speech engines (LiveKit) behind provider ports

**Status:** Accepted
**Date:** 2026-06-01

## Context

ADR-002 established provider **ports** in the domain and **adapters** in infrastructure. It left open *how* each adapter talks to the outside world. Implementing a hand-rolled adapter per provider is weak for two reasons:

1. **LLMs diverge in capability, not just endpoint.** Reasoning models expose different controls — OpenAI-style `reasoning_effort` (discrete `low`/`medium`/`high`), Anthropic-style thinking with an explicit token budget and visible thinking blocks, others with their own thinking config. Tool calling, structured output, and streaming framing also differ. A lowest-common-denominator adapter throws all of that away; a per-provider one is a large, error-prone surface to maintain.
2. **Speech only exists inside a voice pipeline.** STT/TTS are meaningless outside an audio context. They are best handled by a voice-agent framework that already abstracts providers and orchestrates the STT → LLM → TTS pipeline (turn detection, interruptions, VAD).

Both problems are already solved by mature, open tools. Re-implementing them is wasted effort and a maintenance liability.

## Decision

Adapters **delegate to a battle-tested engine** instead of hand-rolling provider integrations. The domain still depends only on the port; the engine is an implementation detail.

### LLM — one gateway

- The `LLMProvider` adapter delegates to **LiteLLM**, which normalizes 100+ providers behind one OpenAI-compatible surface and maps reasoning/thinking controls per provider.
- A **single LLM gateway** (the LiteLLM proxy) serves **every** surface — the HTTP API *and* the realtime voice agent. The agent reaches it through its OpenAI-compatible LLM plugin (`base_url` pointed at the gateway). One control plane for keys, fallbacks, cost, rate limits, and observability. No second LLM configuration to maintain.

### Speech — one abstraction, two modes

- STT/TTS run through the **LiveKit Agents** plugin interface, which is provider-agnostic and supports both modes from the same abstraction:
  - **One-shot** (e.g. "listen to a pronunciation"): the TTS plugin's `synthesize()` / STT plugin's `recognize()` are usable **standalone** — no `AgentSession` or room required.
  - **Realtime** (Leo voice sessions): the same plugins inside the agent pipeline.
- A speech provider is therefore integrated **once** and reused across one-shot and realtime. No duplicated provider code.

### Topology

```
api service     → text features: LLMProvider → LiteLLM gateway
agent service   → voice: LiveKit Agents (LLM via gateway, STT/TTS via plugins)
LLM gateway     → LiteLLM proxy that api AND agent call (co-located, same VPC)
```

### Latency discipline (non-negotiable for voice)

A gateway adds a network hop, and voice is latency-critical. Therefore: the gateway is **co-located in the same region/VPC** as the agent and models (a cross-region hop destroys the latency budget; same-VPC adds single-digit ms); the gateway must **pass token streaming through** without buffering; pick LLM models with sub-300ms time-to-first-token; rely on the framework's preemptive generation.

## Consequences

**Positive:**

- The domain stays clean and provider-agnostic. Choosing or swapping a provider/model is configuration, never code (ADR-002 preserved).
- No double maintenance: one LLM gateway for all surfaces, one speech abstraction for one-shot and realtime.
- Centralized reliability and observability for every LLM call (fallbacks, cost, rate limits, traces).
- The engine choice (LiteLLM vs. alternative, gateway vs. in-process SDK, framework plugin vs. direct SDK) lives **behind the port** — it is reversible without touching domain or application code.

**Negative:**

- Two infrastructure dependencies to operate (the LLM gateway and the voice framework).
- The gateway hop must be managed carefully for voice (mitigated by co-location).
- The speech abstraction is audio-frame oriented; one-shot synthesis must assemble frames into an encoded audio file.

## Alternatives considered

**Hand-rolled per-provider adapters calling each SDK directly.** Maximum control, but a large surface that poorly reinvents reasoning/streaming normalization and ages badly. Rejected.

**A separate "unified speech" library independent of the voice framework.** No dominant, mature option exists; STT/TTS abstraction is the job of the voice-agent framework. Rejected in favor of reusing the one already used for realtime.

**Per-surface LLM clients (one for the API, another for the agent).** Splits keys, cost, and observability across two configurations — double maintenance. Rejected in favor of a single gateway; a latency-critical path may bypass it later if measurement proves it necessary (a config change, not a refactor).
