"""System endpoints: liveness, readiness, and version.

- ``/health/live`` never touches external services (process liveness only).
- ``/health/ready`` checks PostgreSQL and Qdrant with strict timeouts. It must NOT call
  the paid OpenAI API. Returns 503 (naming the failed dependency) when a check fails.
- ``/version`` exposes safe build metadata.

The readiness checks are exposed through the :func:`readiness_checks` dependency so tests
can override them without live services.
"""

import asyncio
from typing import Annotated

import httpx
import psycopg
from fastapi import APIRouter, Depends, Response

from app.core.config import Settings, get_settings

router = APIRouter(tags=["system"])

_DB_TIMEOUT_S = 2.0
_QDRANT_TIMEOUT_S = 2.0

SettingsDep = Annotated[Settings, Depends(get_settings)]


async def check_postgres(settings: Settings) -> dict:
    """Return ``{"ok": bool, ...}`` — never raises."""

    def _probe() -> None:
        with psycopg.connect(settings.psycopg_dsn, connect_timeout=int(_DB_TIMEOUT_S)) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()

    try:
        await asyncio.wait_for(asyncio.to_thread(_probe), timeout=_DB_TIMEOUT_S + 1)
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001 - readiness reports failures, never raises
        return {"ok": False, "error": type(exc).__name__}


async def check_qdrant(settings: Settings) -> dict:
    """Return ``{"ok": bool, ...}`` — never raises."""
    url = settings.qdrant_url.rstrip("/") + "/readyz"
    try:
        async with httpx.AsyncClient(timeout=_QDRANT_TIMEOUT_S) as client:
            resp = await client.get(url)
            resp.raise_for_status()
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": type(exc).__name__}


async def readiness_checks(settings: SettingsDep) -> dict:
    postgres, qdrant = await asyncio.gather(
        check_postgres(settings),
        check_qdrant(settings),
    )
    return {"postgres": postgres, "qdrant": qdrant}


ReadinessDep = Annotated[dict, Depends(readiness_checks)]


@router.get("/health/live")
async def health_live(settings: SettingsDep) -> dict:
    return {"status": "ok", "version": settings.app_version}


@router.get("/health/ready")
async def health_ready(response: Response, checks: ReadinessDep) -> dict:
    all_ok = all(dep.get("ok") for dep in checks.values())
    if not all_ok:
        response.status_code = 503
    return {
        "status": "ready" if all_ok else "degraded",
        "dependencies": checks,
    }


@router.get("/version")
async def version(settings: SettingsDep) -> dict:
    return {"app_version": settings.app_version, "commit": settings.git_commit}
