from fastapi import APIRouter, Request, Response, status

from source.schemas.pydantic.auth import AuthResponse, ForgotPasswordRequest, LoginRequest, LogoutRequest, RefreshTokenRequest, RegisterRequest, ResetPasswordRequest, VerifyEmailRequest
from source.schemas.pydantic.common import ActionResult, SuccessResponse
from source.schemas.pydantic.user import UserProfile
from source.services import AuthUserService

router = APIRouter(prefix="/auth", tags=["auth"])
service = AuthUserService()


def _set_auth_cookies(response: Response, auth_response: AuthResponse) -> None:
    response.set_cookie(
        key=service.access_cookie_name,
        value=auth_response.data.access_token,
        httponly=True,
        secure=False,
        samesite='lax',
        path='/',
    )
    response.set_cookie(
        key=service.refresh_cookie_name,
        value=auth_response.data.refresh_token,
        httponly=True,
        secure=False,
        samesite='lax',
        path='/',
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(service.access_cookie_name, path='/')
    response.delete_cookie(service.refresh_cookie_name, path='/')


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(request: Request, response: Response, payload: RegisterRequest) -> AuthResponse:
    result = await service.register(request, payload)
    _set_auth_cookies(response, result)
    return result


@router.post("/login", response_model=AuthResponse)
async def login(request: Request, response: Response, payload: LoginRequest) -> AuthResponse:
    result = await service.login(request, payload)
    _set_auth_cookies(response, result)
    return result


@router.post("/refresh", response_model=AuthResponse)
async def refresh(request: Request, response: Response, payload: RefreshTokenRequest) -> AuthResponse:
    result = await service.refresh(request, payload)
    _set_auth_cookies(response, result)
    return result


@router.post("/logout", response_model=SuccessResponse[ActionResult])
async def logout(request: Request, response: Response, payload: LogoutRequest) -> SuccessResponse[ActionResult]:
    result = await service.logout(request, payload)
    _clear_auth_cookies(response)
    return result


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
