"""Provider adapters and registries.

Each ``<kind>/`` package holds a registry (``get_<kind>_provider``) that maps
configuration to an adapter, plus the adapters themselves. Today only the
``fake`` adapter ships; LiteLLM (LLM) and LiveKit (TTS/STT) land in #3/#4/B.1.
"""
