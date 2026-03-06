from fastapi import status

from source.config.settings import settings


async def test_user_end_to_end_journey(async_client) -> None:
    register_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/auth/register",
        json={
            'email': 'journey@example.com',
            'username': 'journey_user',
            'password': 'JourneyPass123',
            'locale': 'en',
            'timezone': 'UTC',
        },
    )
    assert register_response.status_code == status.HTTP_201_CREATED

    login_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/auth/login",
        json={'email_or_username': 'journey_user', 'password': 'JourneyPass123'},
    )
    assert login_response.status_code == status.HTTP_200_OK
    token = login_response.json()['data']['access_token']
    headers = {'Authorization': f'Bearer {token}'}

    home_response = await async_client.get('/')
    players_page = await async_client.get('/players')
    player_api = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/players/1")
    assert home_response.status_code == status.HTTP_200_OK
    assert players_page.status_code == status.HTTP_200_OK
    assert player_api.status_code == status.HTTP_200_OK

    favorite_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/users/me/favorites",
        json={'entity_type': 'player', 'entity_id': 1},
        headers=headers,
    )
    assert favorite_response.status_code == status.HTTP_200_OK

    subscription_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/users/me/subscriptions",
        json={'entity_type': 'match', 'entity_id': 2, 'notification_types': ['match_start'], 'channels': ['web']},
        headers=headers,
    )
    assert subscription_response.status_code == status.HTTP_200_OK

    notifications_page = await async_client.get('/notifications')
    notifications_api = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/notifications", headers=headers)
    assert notifications_page.status_code == status.HTTP_200_OK
    assert notifications_api.status_code == status.HTTP_200_OK
