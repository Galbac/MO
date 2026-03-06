# Tennis Portal

FastAPI skeleton теннисного портала, выстроенный по структуре проекта `mediann-vpn`.

## Что есть в репозитории

- `source/api` - public/admin API v1, разбитый по доменам
- `source/interactors` - service-like слой с бизнесовыми mock-операциями
- `source/schemas/pydantic` - request/response контракты для public и admin API
- `source/db/models` - расширенный SQLAlchemy-модельный слой под ключевые сущности ТЗ
- `alembic/versions/0001_initial.py` - стартовая миграция схемы
- `docs/openapi.yaml` - синхронизированный каркас OpenAPI под фактические endpoints
- `source/web` - public/admin HTML frontend scaffold, Jinja-based web-router, static assets и fetch-driven page bootstrap
- `source/tests` - smoke tests для API

## Покрытые модули

- Auth: register/login/refresh/logout/forgot/reset/verify/me
- Users: profile, password, favorites, subscriptions, notifications
- Players: list/detail/stats/matches/ranking-history/titles/news/upcoming/compare/h2h
- Tournaments: list/detail/matches/draw/players/champions/news/calendar
- Matches: list/detail/score/stats/timeline/h2h/preview/point-by-point/upcoming/results
- Live: list/detail/feed + WebSocket stub
- Rankings: list/current/history/player/race
- News: list/detail/categories/tags/featured/related
- Search: global search + suggestions
- Notifications: list/unread-count/read/read-all/test
- Media: upload/get/delete
- Admin: users, players, tournaments, matches, rankings, news, taxonomy, integrations, audit
- Frontend public: home, players, player detail, tournaments, tournament detail, matches, match detail, live, rankings, h2h, news, news detail, search, account, notifications, 404, 500
- Frontend admin: login, dashboard, users, user detail, players, player form, tournaments, tournament form, matches, match detail, live operations, rankings, news, news form, categories, tags, media, notifications, integrations, audit, settings

## Запуск

```bash
poetry install
poetry run uvicorn source.main:create_app --factory --reload
```

## Ограничения текущего skeleton

- interactor-слой пока работает на in-memory mock-данных, без реального repository/service/caching/auth flow
- frontend реализован как Jinja + HTML/CSS/JS scaffold с SSR meta context и клиентской интеграцией в `/api/v1`, но без production state-management, auth guards и полноценного CRUD lifecycle
- OpenAPI расширен как рабочий контрактный каркас, но не заменяет дальнейшую детализацию security/examples/error-codes
