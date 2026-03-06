from fastapi import APIRouter, Request, status

from source.schemas.pydantic.auth import (
    AuthResponse,
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshTokenRequest,
    RegisterRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
)
from source.schemas.pydantic.common import SuccessResponse
from source.schemas.pydantic.user import UserProfile
from source.services import AuthUserService

router = APIRouter(prefix="/auth", tags=["auth"])
service = AuthUserService()


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest) -> AuthResponse:
    return await service.register(payload)


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest) -> AuthResponse:
    return await service.login(payload)


@router.post("/refresh", response_model=AuthResponse)
async def refresh(payload: RefreshTokenRequest) -> AuthResponse:
    return await service.refresh(payload)


@router.post("/logout", response_model=MessageResponse)
async def logout(payload: LogoutRequest) -> MessageResponse:
    return await service.logout(payload)


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(payload: ForgotPasswordRequest) -> MessageResponse:
    return await service.forgot_password(payload)


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(payload: ResetPasswordRequest) -> MessageResponse:
    return await service.reset_password(payload)


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(payload: VerifyEmailRequest) -> MessageResponse:
    return await service.verify_email(payload)


@router.get("/me", response_model=SuccessResponse[UserProfile])
async def auth_me(request: Request) -> SuccessResponse[UserProfile]:
    return await service.auth_me(request)
