from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from source.schemas.pydantic.common import ErrorItem


def _error_response(status_code: int, code: str, message: str, field: str | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "data": None,
            "meta": {},
            "errors": [ErrorItem(code=code, message=message, field=field).model_dump()],
        },
    )


def _friendly_message(status_code: int, detail: str | None = None) -> str:
    raw = (detail or '').strip()
    normalized = raw.lower()
    translations = {
        'authentication required': 'Нужно войти в аккаунт, чтобы продолжить.',
        'invalid credentials': 'Неверный логин или пароль.',
        'user not found': 'Пользователь не найден.',
        'user is not active': 'Аккаунт временно недоступен. Обратитесь в поддержку.',
        'insufficient permissions': 'У вас нет прав для этого действия.',
        'email already exists': 'Пользователь с такой почтой уже зарегистрирован.',
        'username already exists': 'Это имя пользователя уже занято.',
        'privacy consent is required': 'Подтвердите согласие на обработку персональных данных.',
        'unsupported timezone': 'Указан неподдерживаемый часовой пояс.',
        'weak password': 'Пароль слишком простой. Используйте не менее 8 символов, буквы и цифры.',
        'too many login attempts': 'Слишком много попыток входа. Попробуйте еще раз немного позже.',
        'invalid refresh token': 'Сессия устарела. Войдите заново.',
        'refresh token revoked': 'Сессия завершена. Войдите заново.',
        'invalid access token': 'Сессия устарела. Войдите заново.',
        'token is required': 'Не хватает обязательных данных для выполнения действия.',
        'invalid token': 'Ссылка или токен больше не действуют.',
        'token not found': 'Ссылка подтверждения больше не действительна.',
        'token already used': 'Эта ссылка уже была использована.',
        'token expired': 'Срок действия ссылки истек. Запросите новую.',
        'current password is invalid': 'Текущий пароль указан неверно.',
        'unsupported maintenance job type': 'Такую служебную операцию сейчас выполнить нельзя.',
    }
    if normalized in translations:
        return translations[normalized]
    if status_code == status.HTTP_500_INTERNAL_SERVER_ERROR:
        return 'Сервис временно недоступен. Попробуйте еще раз чуть позже.'
    if status_code == status.HTTP_404_NOT_FOUND:
        return 'Нужные данные не найдены или уже были удалены.'
    if status_code == status.HTTP_403_FORBIDDEN:
        return 'У вас нет доступа к этому разделу.'
    if status_code == status.HTTP_401_UNAUTHORIZED:
        return 'Нужно войти в аккаунт, чтобы продолжить.'
    if status_code == status.HTTP_422_UNPROCESSABLE_ENTITY:
        return raw or 'Проверьте заполненные поля и попробуйте еще раз.'
    return raw or 'Не удалось выполнить запрос. Попробуйте еще раз.'


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def handle_http_exception(_: Request, exc: HTTPException) -> JSONResponse:
        return _error_response(
            status_code=exc.status_code,
            code="HTTP_ERROR",
            message=_friendly_message(exc.status_code, str(exc.detail)),
        )

    @app.exception_handler(ValidationError)
    async def handle_validation_error(_: Request, exc: ValidationError) -> JSONResponse:
        first_error = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(item) for item in first_error.get("loc", [])) or None
        return _error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="VALIDATION_ERROR",
            message=_friendly_message(status.HTTP_422_UNPROCESSABLE_ENTITY, first_error.get("msg", "Validation error")),
            field=field,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(_: Request, __: Exception) -> JSONResponse:
        return _error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="INTERNAL_ERROR",
            message=_friendly_message(status.HTTP_500_INTERNAL_SERVER_ERROR),
        )
