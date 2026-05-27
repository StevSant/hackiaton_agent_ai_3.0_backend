from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import get_login_use_case
from app.schemas.auth import LoginRequest, LoginResponse
from app.use_cases.auth.login import LoginUseCase

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login_json(
    body: LoginRequest,
    use_case: Annotated[LoginUseCase, Depends(get_login_use_case)],
) -> LoginResponse:
    """JSON login endpoint — used by the Angular frontend."""
    return use_case.execute(email=body.email, password=body.password)


@router.post("/token", response_model=LoginResponse)
def login_form(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    use_case: Annotated[LoginUseCase, Depends(get_login_use_case)],
) -> LoginResponse:
    """OAuth2 form login — enables the 'Authorize' button in Swagger UI."""
    return use_case.execute(email=form.username, password=form.password)
