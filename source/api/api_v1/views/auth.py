from fastapi import APIRouter, Request, status

from source.schemas.pydantic.auth import AuthResponse, ForgotPasswordRequest, LoginRequest, LogoutRequest, RefreshTokenRequest, RegisterRequest, ResetPasswordRequest, VerifyEmailRequest
from source.schemas.pydantic.common import ActionResult, SuccessResponse
from source.schemas.pydantic.user import UserProfile
from source.services import AuthUserService

router = APIRouter(prefix="/auth", tags=["auth"])
service = AuthUserService()


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(request: Request, payload: RegisterRequest) -> AuthResponse:
    return await service.register(request, payload)


@router.post("/login", response_model=AuthResponse)
async def login(request: Request, payload: LoginRequest) -> AuthResponse:
    return await service.login(request, payload)


@router.post("/refresh", response_model=AuthResponse)
async def refresh(request: Request, payload: RefreshTokenRequest) -> AuthResponse:
    return await service.refresh(request, payload)


@router.post("/logout", response_model=SuccessResponse[ActionResult])
async def logout(request: Request, payload: LogoutRequest) -> SuccessResponse[ActionResult]:
    return await service.logout(request, payload)


@router.post("/forgot-password", response_model=SuccessResponse[ActionResult])
async def forgot_password(request: Request, payload: ForgotPasswordRequest) -> SuccessResponse[ActionResult]:
    return await service.forgot_password(request, payload)


@router.post("/reset-password", response_model=SuccessResponse[ActionResult])
async def reset_password(payload: ResetPasswordRequest) -> SuccessResponse[ActionResult]:
    return await service.reset_password(payload)


@router.post("/verify-email", response_model=SuccessResponse[ActionResult])
async def verify_email(payload: VerifyEmailRequest) -> SuccessResponse[ActionResult]:
    return await service.verify_email(payload)


@router.get("/me", response_model=SuccessResponse[UserProfile])
async def auth_me(request: Request) -> SuccessResponse[UserProfile]:
    return await service.auth_me(request)
