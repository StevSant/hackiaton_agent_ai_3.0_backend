from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class CurrentUser(BaseModel):
    id: str
    email: str
    role: str
    full_name: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 28800  # 480 min default
    user: CurrentUser


class TokenPayload(BaseModel):
    sub: str  # user UUID
    email: str
    role: str
    full_name: str
