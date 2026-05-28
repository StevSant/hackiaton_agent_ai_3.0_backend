"""Asegurados API — THIN router.

Routes:
    GET    /asegurados        → list[AseguradoOut]  (any authenticated user)
    POST   /asegurados        → AseguradoOut        (analista | antifraude)
    PATCH  /asegurados/{id}    → AseguradoOut        (analista | antifraude)
    DELETE /asegurados/{id}    → 204                 (analista | antifraude)

Single-record management complements the bulk import flow. Mutations are open to
both authenticated roles (master-data curation is not a single-role action).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.cache_control import cache_for
from app.api.deps import get_current_user, require_any_role
from app.domain.auth.role import Role
from app.domain.auth.user import User
from app.infrastructure.db.engine import get_session
from app.schemas.asegurados import AseguradoCreate, AseguradoOut, AseguradoUpdate
from app.use_cases.create_asegurado import create_asegurado
from app.use_cases.delete_asegurado import delete_asegurado
from app.use_cases.list_asegurados import list_asegurados
from app.use_cases.update_asegurado import update_asegurado

router = APIRouter(prefix="/asegurados", tags=["asegurados"])

_manage = require_any_role(Role.analista, Role.antifraude)


@router.get(
    "",
    response_model=list[AseguradoOut],
    dependencies=[Depends(cache_for(30))],
)
async def list_asegurados_route(
    session: Annotated[AsyncSession, Depends(get_session)],
    _user: Annotated[User, Depends(get_current_user)] = ...,  # type: ignore[assignment]
) -> list[AseguradoOut]:
    return await list_asegurados(session)


@router.post(
    "",
    response_model=AseguradoOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_manage)],
)
async def create_asegurado_route(
    body: AseguradoCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AseguradoOut:
    return await create_asegurado(session, body)


@router.patch(
    "/{id_asegurado}",
    response_model=AseguradoOut,
    dependencies=[Depends(_manage)],
)
async def update_asegurado_route(
    id_asegurado: str,
    body: AseguradoUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AseguradoOut:
    return await update_asegurado(session, id_asegurado, body)


@router.delete(
    "/{id_asegurado}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(_manage)],
)
async def delete_asegurado_route(
    id_asegurado: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    await delete_asegurado(session, id_asegurado)
