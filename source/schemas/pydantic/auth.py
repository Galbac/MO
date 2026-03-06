from pydantic import BaseModel, EmailStr, Field

from source.schemas.pydantic.common import SuccessResponse
from source.schemas.pydantic.user import UserTokenBundle


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8)
    locale: str | None = None
    timezone: str | None = None


class LoginRequest(BaseModel):
    email_or_username: str
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8)


class VerifyEmailRequest(BaseModel):
    token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class SimpleMessage(BaseModel):
    message: str


class AuthResponse(SuccessResponse[UserTokenBundle]):
    pass


class MessageResponse(SuccessResponse[SimpleMessage]):
    pass
