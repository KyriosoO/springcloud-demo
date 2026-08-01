from __future__ import annotations

from fastapi import APIRouter, Request, Response

router = APIRouter()


@router.get("/internal/health/live", response_class=Response)
async def live() -> Response:
    return Response(status_code=200)


@router.get("/internal/health/ready", response_class=Response)
async def ready(request: Request) -> Response:
    return Response(status_code=200 if request.app.state.ready else 503)
