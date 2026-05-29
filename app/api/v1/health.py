from fastapi import APIRouter, Depends

from app import __version__
from app.api.deps import Settings, get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    return {"version": __version__, "env": settings.ENV}
