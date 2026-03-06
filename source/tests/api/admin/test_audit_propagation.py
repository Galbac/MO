from fastapi import status

from source.config.settings import settings


async def test_user_profile_update_creates_audit_log(async_client, user_auth_headers, admin_auth_headers) -> None:
    response = await async_client.patch(
        f"{settings.api.prefix}{settings.api.v1.prefix}/users/me",
        json={"first_name": "Audited"},
        headers=user_auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK

    audit_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/audit-logs", headers=admin_auth_headers)
    assert audit_response.status_code == status.HTTP_200_OK
    assert any(item["action"] == "user.update_profile" for item in audit_response.json()["data"])


async def test_admin_content_update_creates_audit_log(async_client, admin_auth_headers) -> None:
    create_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/players",
        json={"first_name": "Audit", "last_name": "Player", "full_name": "Audit Player", "slug": "audit-player", "country_code": "ESP"},
        headers=admin_auth_headers,
    )
    assert create_response.status_code == status.HTTP_200_OK
    player_id = create_response.json()["data"]["id"]

    audit_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/audit-logs", headers=admin_auth_headers)
    assert audit_response.status_code == status.HTTP_200_OK
    assert any(item["action"] == "player.create" and item["entity_id"] == player_id for item in audit_response.json()["data"])


async def test_admin_user_update_creates_audit_log(async_client, admin_auth_headers) -> None:
    response = await async_client.patch(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/users/2",
        json={"status": "blocked"},
        headers=admin_auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK

    audit_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/audit-logs", headers=admin_auth_headers)
    assert audit_response.status_code == status.HTTP_200_OK
    assert any(item["action"] == "admin.user.update" and item["entity_id"] == 2 for item in audit_response.json()["data"])
