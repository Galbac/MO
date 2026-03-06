from source.config.settings import settings


async def test_public_api_load_smoke(async_client) -> None:
    endpoints = [
        f"{settings.api.prefix}{settings.api.v1.prefix}/live",
        f"{settings.api.prefix}{settings.api.v1.prefix}/matches/2",
        f"{settings.api.prefix}{settings.api.v1.prefix}/players",
        f"{settings.api.prefix}{settings.api.v1.prefix}/rankings/current",
    ]

    responses = []
    for _ in range(8):
        for path in endpoints:
            responses.append(await async_client.get(path))

    assert all(response.status_code == 200 for response in responses)
    assert any(response.json().get('data') for response in responses)


async def test_authenticated_api_load_smoke(async_client, user_auth_headers) -> None:
    endpoints = [
        f"{settings.api.prefix}{settings.api.v1.prefix}/users/me",
        f"{settings.api.prefix}{settings.api.v1.prefix}/users/me/notifications",
        f"{settings.api.prefix}{settings.api.v1.prefix}/notifications/unread-count",
    ]

    responses = []
    for _ in range(6):
        for path in endpoints:
            responses.append(await async_client.get(path, headers=user_auth_headers))

    assert all(response.status_code == 200 for response in responses)
