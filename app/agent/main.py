"""Voice agent worker entrypoint (#15).

Runs Leo's realtime loop via LiveKit Agents. Two modes, both off this one file
(``cli.run_app`` parses the subcommand from argv):

- ``python -m app.agent.main console`` — local mic/speaker, no room, no frontend.
  The dev round trip. Needs no LiveKit credentials.
- ``python -m app.agent.main dev`` — connects to a LiveKit server and handles
  room dispatches. Same code path as production.

A keyless boot (``*_PROVIDER=fake``) wires the pipeline with the construct-only
fakes — useful to validate config/wiring. A live console/`dev` round trip uses
real engines: a local LiteLLM gateway + LiveKit server + provider keys.
"""

from __future__ import annotations

from livekit.agents import JobContext, JobProcess, WorkerOptions, cli

# Import the engine plugins at module top so each registers on the main thread
# (LiveKit requires plugin registration there). prewarm/entrypoint run in job
# threads/processes, where a first-time plugin import would raise; here the
# registration is already done and those imports just hit the module cache.
from livekit.plugins import elevenlabs, openai, silero  # noqa: F401

from app.agent.leo import load_leo
from app.agent.pipeline import build_session
from app.core.config import Settings, get_settings

_LIVEKIT_CREDS = ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET")


def require_livekit_creds(settings: Settings) -> None:
    """Fail fast if a real deployment is missing LiveKit room credentials.

    Lives here (the agent's boot path), not in the shared ``Settings`` validator:
    the api service runs in staging/production without LiveKit creds, so the
    shared validator must not require them.
    """
    if settings.ENV not in ("staging", "production"):
        return
    missing = [name for name in _LIVEKIT_CREDS if not getattr(settings, name)]
    if missing:
        raise ValueError(
            f"LiveKit credentials required when ENV={settings.ENV}: "
            + ", ".join(missing)
        )


def _prewarm(proc: JobProcess) -> None:
    """Load the Silero VAD once per worker process (heavy) and reuse it across
    jobs. Skipped in fake STT mode, which uses a no-load fake VAD."""
    settings = get_settings()
    if settings.STT_PROVIDER != "fake":
        from livekit.plugins import silero

        proc.userdata["vad"] = silero.VAD.load()


async def _entrypoint(ctx: JobContext) -> None:
    settings = get_settings()
    await ctx.connect()
    session = build_session(settings, vad=ctx.proc.userdata.get("vad"))
    await session.start(agent=load_leo(settings), room=ctx.room)


def worker_options(settings: Settings) -> WorkerOptions:
    """Build the worker config from settings (room creds flow to ``dev`` mode;
    ``console`` ignores them). Factored out so tests can assert it builds."""
    return WorkerOptions(
        entrypoint_fnc=_entrypoint,
        prewarm_fnc=_prewarm,
        ws_url=settings.LIVEKIT_URL or "",
        api_key=settings.LIVEKIT_API_KEY or "",
        api_secret=settings.LIVEKIT_API_SECRET or "",
    )


if __name__ == "__main__":
    _settings = get_settings()
    require_livekit_creds(_settings)
    cli.run_app(worker_options(_settings))
