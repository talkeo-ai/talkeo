from app.core.config import Settings, get_settings

__all__ = ["Settings", "get_settings"]

# Future dependency providers (LLM, STT, TTS, repositories) will be added here
# and consumed by routers via fastapi.Depends.
