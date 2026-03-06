from fastapi import status

from source.config.settings import settings


async def test_admin_users_returns_list(async_client, admin_auth_headers) -> None:
    response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/users", headers=admin_auth_headers)

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"][0]["role"] == "admin"


async def test_admin_user_update_persists_changes(async_client, admin_auth_headers) -> None:
    response = await async_client.patch(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/users/2",
        json={"role": "editor", "status": "blocked"},
        headers=admin_auth_headers,
    )

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["data"]["role"] == "editor"
    assert payload["data"]["status"] == "blocked"
