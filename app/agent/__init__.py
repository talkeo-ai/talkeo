"""Voice agent service (LiveKit Agents worker).

Sibling to the ``api`` service: same repo, same ``Settings``, same LiteLLM
gateway (ADR-008). The agent runs Leo's realtime voice loop by wiring LiveKit
plugins (STT/LLM/TTS/VAD) into an ``AgentSession``. The worker entrypoint and
persona land in #15's follow-up PR; this package currently ships the pipeline
builder and keyless fake plugins.
"""
