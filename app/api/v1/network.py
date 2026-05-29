"""Network / providers API — THIN router.

Routes:
    GET    /network/providers          → list[ProviderOut]  (any authenticated user)
    POST   /network/providers          → ProviderOut        (analista | antifraude)
    PATCH  /network/providers/{id}     → ProviderOut        (analista | antifraude)
    DELETE /network/providers/{id}     → 204                (analista | antifraude)

Single-record management complements the bulk import flow — master data can be
curated one row at a time. Mutations are open to both authenticated roles
(master-data curation is not a single-role action); claim-workflow RBAC is
unaffected.
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
from app.schemas.network import (
    NetworkRelations,
    ProviderCreate,
    ProviderOut,
    ProviderUpdate,
)
from app.use_cases.create_provider import create_provider
from app.use_cases.delete_provider import delete_provider
from app.use_cases.list_providers import list_providers
from app.use_cases.network_relations import network_relations
from app.use_cases.update_provider import update_provider

router = APIRouter(prefix="/network", tags=["network"])

_manage = require_any_role(Role.analista, Role.antifraude)


@router.get(
    "/providers",
    response_model=list[ProviderOut],
    dependencies=[Depends(cache_for(30))],
)
async def list_providers_route(
    session: Annotated[AsyncSession, Depends(get_session)],
    _user: Annotated[User, Depends(get_current_user)] = ...,  # type: ignore[assignment]
) -> list[ProviderOut]:
    return await list_providers(session)


@router.get(
    "/relations",
    response_model=NetworkRelations,
    dependencies=[Depends(cache_for(30))],
)
async def network_relations_route(
    session: Annotated[AsyncSession, Depends(get_session)],
    _user: Annotated[User, Depends(get_current_user)] = ...,  # type: ignore[assignment]
) -> NetworkRelations:
    return await network_relations(session)


@router.post(
    "/providers",
    response_model=ProviderOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_manage)],
)
async def create_provider_route(
    body: ProviderCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProviderOut:
    return await create_provider(session, body)


@router.patch(
    "/providers/{id_proveedor}",
    response_model=ProviderOut,
    dependencies=[Depends(_manage)],
)
async def update_provider_route(
    id_proveedor: str,
    body: ProviderUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProviderOut:
    return await update_provider(session, id_proveedor, body)


@router.delete(
    "/providers/{id_proveedor}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(_manage)],
)
async def delete_provider_route(
    id_proveedor: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    await delete_provider(session, id_proveedor)
