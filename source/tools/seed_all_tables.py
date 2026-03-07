from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select

from source.db.bootstrap import _seed_hash_password, seed_demo_data
from source.db.models import (
    AuditLog,
    FavoriteEntity,
    HeadToHead,
    Match,
    MatchEvent,
    MatchSet,
    MatchStats,
    NewsArticle,
    NewsCategory,
    Notification,
    NotificationSubscription,
    Player,
    RankingSnapshot,
    Tag,
    Tournament,
    User,
)
from source.db.session import db_session_manager


TARGET_ROWS = 10


async def _count(session, model) -> int:
    return int((await session.scalar(select(func.count()).select_from(model))) or 0)


async def _next_id(session, model) -> int:
    return int((await session.scalar(select(func.max(model.id)))) or 0) + 1


async def _ids(session, model) -> list[int]:
    return list((await session.scalars(select(model.id).order_by(model.id))).all())


async def _ensure_users(session) -> None:
    now = datetime.now(tz=UTC)
    core_accounts = [
        {
            "email": "admin@makhachkalaopen.ru",
            "username": "admin",
            "password": "AdminPass123",
            "role": "admin",
            "first_name": "Главный",
            "last_name": "Администратор",
        },
        {
            "email": "user@makhachkalaopen.ru",
            "username": "demo_user",
            "password": "UserPass123",
            "role": "user",
            "first_name": "Демо",
            "last_name": "Пользователь",
        },
        {
            "email": "editor@makhachkalaopen.ru",
            "username": "editor",
            "password": "EditorPass123",
            "role": "editor",
            "first_name": "Спортивный",
            "last_name": "Редактор",
        },
        {
            "email": "operator@makhachkalaopen.ru",
            "username": "operator",
            "password": "OperatorPass123",
            "role": "operator",
            "first_name": "Лайв",
            "last_name": "Оператор",
        },
    ]

    next_id = await _next_id(session, User)
    for account in core_accounts:
        user = await session.scalar(select(User).where(User.username == account["username"]))
        if user is None:
            user = await session.scalar(select(User).where(User.email == account["email"]))
        if user is None:
            session.add(
                User(
                    id=next_id,
                    email=account["email"],
                    username=account["username"],
                    password_hash=_seed_hash_password(account["password"]),
                    role=account["role"],
                    status="active",
                    first_name=account["first_name"],
                    last_name=account["last_name"],
                    locale="ru",
                    timezone="Europe/Moscow",
                    is_email_verified=True,
                    privacy_consent=True,
                    privacy_consent_at=now,
                )
            )
            next_id += 1
            continue

        user.email = account["email"]
        user.username = account["username"]
        user.password_hash = _seed_hash_password(account["password"])
        user.role = account["role"]
        user.status = "active"
        user.first_name = account["first_name"]
        user.last_name = account["last_name"]
        user.locale = "ru"
        user.timezone = "Europe/Moscow"
        user.is_email_verified = True
        user.privacy_consent = True
        user.privacy_consent_at = user.privacy_consent_at or now

    await session.flush()

    count = await _count(session, User)
    next_id = await _next_id(session, User)
    roles = ["user", "editor", "operator", "user", "user", "editor"]
    for index in range(count + 1, TARGET_ROWS + 1):
        session.add(
            User(
                id=next_id,
                email=f"user{index}@makhachkalaopen.ru",
                username=f"user_{index}",
                password_hash=_seed_hash_password(f"UserPass{100 + index}"),
                role=roles[(index - count - 1) % len(roles)],
                status="active",
                first_name=f"Пользователь {index}",
                last_name="Портала",
                locale="ru",
                timezone="Europe/Moscow",
                is_email_verified=True,
                privacy_consent=True,
                privacy_consent_at=now,
            )
        )
        next_id += 1


async def _ensure_categories_and_tags(session) -> None:
    category_count = await _count(session, NewsCategory)
    category_next_id = await _next_id(session, NewsCategory)
    for index in range(category_count + 1, TARGET_ROWS + 1):
        session.add(NewsCategory(id=category_next_id, slug=f"category-{index}", name=f"Категория {index}"))
        category_next_id += 1

    tag_count = await _count(session, Tag)
    tag_next_id = await _next_id(session, Tag)
    for index in range(tag_count + 1, TARGET_ROWS + 1):
        session.add(Tag(id=tag_next_id, slug=f"tag-{index}", name=f"Тег {index}"))
        tag_next_id += 1


async def _ensure_players(session) -> None:
    count = await _count(session, Player)
    next_id = await _next_id(session, Player)
    for index in range(count + 1, TARGET_ROWS + 1):
        session.add(
            Player(
                id=next_id,
                slug=f"player-{index}",
                first_name=f"Игрок {index}",
                last_name="Махачкала",
                full_name=f"Игрок {index} Махачкала",
                country_code="RUS",
                country_name="Россия",
                birth_date=date(1995 + index % 8, (index % 12) + 1, (index % 27) + 1),
                height_cm=178 + index,
                weight_kg=68 + index,
                hand="right",
                backhand="two-handed",
                biography=f"Профиль игрока {index} для демонстрации статистики, рейтингов и новостей.",
                photo_url=f"/media/players/player-{index}.jpg",
                status="active",
                current_rank=index,
                current_points=5000 - index * 90,
            )
        )
        next_id += 1


async def _ensure_tournaments(session) -> None:
    count = await _count(session, Tournament)
    next_id = await _next_id(session, Tournament)
    categories = ["grand_slam", "masters_1000", "atp_500", "wta_500", "challenger"]
    surfaces = ["hard", "clay", "grass"]
    statuses = ["scheduled", "live", "finished"]
    for index in range(count + 1, TARGET_ROWS + 1):
        session.add(
            Tournament(
                id=next_id,
                slug=f"tournament-{index}",
                name=f"Турнир {index}",
                short_name=f"Т-{index}",
                category=categories[(index - 1) % len(categories)],
                surface=surfaces[(index - 1) % len(surfaces)],
                indoor=index % 2 == 0,
                city=f"Город {index}",
                country_code="RUS",
                prize_money=f"${1_000_000 + index * 125_000}",
                points_winner=250 + index * 25,
                season_year=2026,
                start_date=date(2026, ((index - 1) % 12) + 1, 1 + (index % 12)),
                end_date=date(2026, ((index - 1) % 12) + 1, 5 + (index % 20)),
                status=statuses[(index - 1) % len(statuses)],
                logo_url=f"/media/tournaments/tournament-{index}.png",
                description=f"Описание турнира {index} для календаря, сетки и карточки соревнования.",
            )
        )
        next_id += 1


async def _ensure_matches(session) -> None:
    count = await _count(session, Match)
    next_id = await _next_id(session, Match)
    player_ids = await _ids(session, Player)
    tournament_ids = await _ids(session, Tournament)
    base_time = datetime(2026, 3, 7, 12, 0, tzinfo=UTC)
    statuses = ["scheduled", "live", "finished"]
    for index in range(count + 1, TARGET_ROWS + 1):
        player1_id = player_ids[(index - 1) % len(player_ids)]
        player2_id = player_ids[index % len(player_ids)]
        if player1_id == player2_id:
            player2_id = player_ids[(index + 1) % len(player_ids)]
        status_value = statuses[(index - 1) % len(statuses)]
        start_at = base_time + timedelta(hours=index)
        session.add(
            Match(
                id=next_id,
                slug=f"match-{index}",
                tournament_id=tournament_ids[(index - 1) % len(tournament_ids)],
                round_code=["R32", "R16", "QF", "SF", "F"][(index - 1) % 5],
                best_of_sets=3,
                player1_id=player1_id,
                player2_id=player2_id,
                winner_id=player1_id if status_value == "finished" else None,
                status=status_value,
                scheduled_at=start_at,
                actual_start_at=start_at if status_value in {"live", "finished"} else None,
                actual_end_at=start_at + timedelta(minutes=105) if status_value == "finished" else None,
                court_name=f"Корт {index}",
                score_summary="6-4 6-4" if status_value == "finished" else "3-2",
            )
        )
        next_id += 1


async def _ensure_match_sets(session) -> None:
    count = await _count(session, MatchSet)
    next_id = await _next_id(session, MatchSet)
    match_ids = await _ids(session, Match)
    for index in range(count + 1, TARGET_ROWS + 1):
        session.add(
            MatchSet(
                id=next_id,
                match_id=match_ids[(index - 1) % len(match_ids)],
                set_number=(index - 1) % 3 + 1,
                player1_games=6 if index % 2 else 4,
                player2_games=4 if index % 2 else 6,
                tiebreak_player1_points=None,
                tiebreak_player2_points=None,
                is_finished=index % 3 != 0,
            )
        )
        next_id += 1


async def _ensure_match_stats(session) -> None:
    existing_match_ids = set((await session.scalars(select(MatchStats.match_id))).all())
    next_id = await _next_id(session, MatchStats)
    for match_id in await _ids(session, Match):
        if await _count(session, MatchStats) >= TARGET_ROWS:
            break
        if match_id in existing_match_ids:
            continue
        session.add(
            MatchStats(
                id=next_id,
                match_id=match_id,
                player1_aces=5 + match_id,
                player2_aces=3 + match_id,
                player1_double_faults=match_id % 4,
                player2_double_faults=(match_id + 1) % 4,
                player1_first_serve_pct=62 + match_id % 9,
                player2_first_serve_pct=59 + match_id % 8,
                player1_break_points_saved=2 + match_id % 5,
                player2_break_points_saved=1 + match_id % 4,
                duration_minutes=85 + match_id * 3,
            )
        )
        next_id += 1


async def _ensure_match_events(session) -> None:
    count = await _count(session, MatchEvent)
    next_id = await _next_id(session, MatchEvent)
    match_ids = await _ids(session, Match)
    player_ids = await _ids(session, Player)
    now = datetime.now(tz=UTC)
    events = ["point", "break_point", "set_finished", "match_finished", "ace"]
    for index in range(count + 1, TARGET_ROWS + 1):
        session.add(
            MatchEvent(
                id=next_id,
                match_id=match_ids[(index - 1) % len(match_ids)],
                event_type=events[(index - 1) % len(events)],
                set_number=(index - 1) % 3 + 1,
                game_number=(index - 1) % 12 + 1,
                player_id=player_ids[(index - 1) % len(player_ids)],
                payload_json={"message": f"Событие {index}", "score": f"{(index + 1) % 7}-{index % 7}"},
                created_at=now - timedelta(minutes=index * 3),
            )
        )
        next_id += 1


async def _ensure_head_to_head(session) -> None:
    count = await _count(session, HeadToHead)
    next_id = await _next_id(session, HeadToHead)
    match_ids = await _ids(session, Match)
    player_ids = await _ids(session, Player)
    for index in range(count + 1, TARGET_ROWS + 1):
        player1_id = player_ids[(index - 1) % len(player_ids)]
        player2_id = player_ids[index % len(player_ids)]
        if player1_id == player2_id:
            player2_id = player_ids[(index + 1) % len(player_ids)]
        session.add(
            HeadToHead(
                id=next_id,
                player1_id=player1_id,
                player2_id=player2_id,
                total_matches=2 + index,
                player1_wins=1 + index % 4,
                player2_wins=index % 3,
                hard_player1_wins=index % 3,
                hard_player2_wins=index % 2,
                clay_player1_wins=index % 2,
                clay_player2_wins=index % 2,
                grass_player1_wins=0,
                grass_player2_wins=0,
                last_match_id=match_ids[(index - 1) % len(match_ids)],
            )
        )
        next_id += 1


async def _ensure_rankings(session) -> None:
    count = await _count(session, RankingSnapshot)
    next_id = await _next_id(session, RankingSnapshot)
    player_ids = await _ids(session, Player)
    ranking_types = ["atp", "wta"]
    for index in range(count + 1, TARGET_ROWS + 1):
        session.add(
            RankingSnapshot(
                id=next_id,
                ranking_type=ranking_types[(index - 1) % len(ranking_types)],
                ranking_date=f"2026-03-{(index % 28) + 1:02d}",
                player_id=player_ids[(index - 1) % len(player_ids)],
                rank_position=index,
                points=9000 - index * 110,
                movement=(index % 5) - 2,
            )
        )
        next_id += 1


async def _ensure_news(session) -> None:
    count = await _count(session, NewsArticle)
    next_id = await _next_id(session, NewsArticle)
    category_ids = await _ids(session, NewsCategory)
    user_ids = await _ids(session, User)
    now = datetime.now(tz=UTC)
    for index in range(count + 1, TARGET_ROWS + 1):
        session.add(
            NewsArticle(
                id=next_id,
                slug=f"news-{index}",
                title=f"Новость турнира {index}",
                subtitle=f"Краткий подзаголовок материала {index}",
                lead=f"Это вводный абзац для материала {index}, который нужен для заполнения карточек и списков.",
                content_html=f"<p>Материал {index} подготовлен для демонстрации редакционного раздела портала.</p>",
                cover_image_url=f"/media/news/news-{index}.jpg",
                author_id=user_ids[(index - 1) % len(user_ids)],
                category_id=category_ids[(index - 1) % len(category_ids)],
                status="published",
                seo_title=f"SEO заголовок новости {index}",
                seo_description=f"SEO описание новости {index} для поисковой выдачи и карточек в соцсетях.",
                published_at=now - timedelta(hours=index),
            )
        )
        next_id += 1


async def _ensure_favorites(session) -> None:
    count = await _count(session, FavoriteEntity)
    next_id = await _next_id(session, FavoriteEntity)
    user_ids = await _ids(session, User)
    player_ids = await _ids(session, Player)
    tournament_ids = await _ids(session, Tournament)
    entity_types = ["player", "tournament"]
    for index in range(count + 1, TARGET_ROWS + 1):
        entity_type = entity_types[(index - 1) % len(entity_types)]
        entity_id = player_ids[(index - 1) % len(player_ids)] if entity_type == "player" else tournament_ids[(index - 1) % len(tournament_ids)]
        session.add(
            FavoriteEntity(
                id=next_id,
                user_id=user_ids[(index - 1) % len(user_ids)],
                entity_type=entity_type,
                entity_id=entity_id,
            )
        )
        next_id += 1


async def _ensure_subscriptions_and_notifications(session) -> None:
    sub_count = await _count(session, NotificationSubscription)
    sub_next_id = await _next_id(session, NotificationSubscription)
    notif_count = await _count(session, Notification)
    notif_next_id = await _next_id(session, Notification)
    user_ids = await _ids(session, User)
    player_ids = await _ids(session, Player)
    now = datetime.now(tz=UTC)

    for index in range(sub_count + 1, TARGET_ROWS + 1):
        session.add(
            NotificationSubscription(
                id=sub_next_id,
                user_id=user_ids[(index - 1) % len(user_ids)],
                entity_type="player",
                entity_id=player_ids[(index - 1) % len(player_ids)],
                notification_types=["match_start", "ranking_change"],
                channels=["web", "email"],
                is_active=True,
            )
        )
        sub_next_id += 1

    for index in range(notif_count + 1, TARGET_ROWS + 1):
        session.add(
            Notification(
                id=notif_next_id,
                user_id=user_ids[(index - 1) % len(user_ids)],
                type=["match_start", "news", "ranking_change"][(index - 1) % 3],
                title=f"Уведомление {index}",
                body=f"Сервисное уведомление {index} для демонстрации центра оповещений.",
                payload_json={"entity_type": "player", "entity_id": player_ids[(index - 1) % len(player_ids)]},
                status="unread" if index % 2 else "read",
                read_at=None if index % 2 else now - timedelta(minutes=index),
            )
        )
        notif_next_id += 1


async def _ensure_audit_logs(session) -> None:
    count = await _count(session, AuditLog)
    next_id = await _next_id(session, AuditLog)
    user_ids = await _ids(session, User)
    now = datetime.now(tz=UTC)
    for index in range(count + 1, TARGET_ROWS + 1):
        session.add(
            AuditLog(
                id=next_id,
                user_id=user_ids[(index - 1) % len(user_ids)],
                action=f"demo.action.{index}",
                entity_type=["player", "tournament", "news", "match"][(index - 1) % 4],
                entity_id=index,
                before_json={"status": "before", "index": index},
                after_json={"status": "after", "index": index},
                created_at=now - timedelta(minutes=index * 5),
                updated_at=now - timedelta(minutes=index * 5),
            )
        )
        next_id += 1


async def seed_all_tables() -> None:
    await db_session_manager.init_models()
    async with db_session_manager.session() as session:
        await seed_demo_data(session, force=True)
        await _ensure_users(session)
        await _ensure_categories_and_tags(session)
        await _ensure_players(session)
        await _ensure_tournaments(session)
        await session.flush()
        await _ensure_matches(session)
        await session.flush()
        await _ensure_match_sets(session)
        await _ensure_match_stats(session)
        await _ensure_match_events(session)
        await _ensure_head_to_head(session)
        await _ensure_rankings(session)
        await _ensure_news(session)
        await _ensure_favorites(session)
        await _ensure_subscriptions_and_notifications(session)
        await _ensure_audit_logs(session)
        await session.commit()

        tables = [
            ("users", User),
            ("players", Player),
            ("tournaments", Tournament),
            ("matches", Match),
            ("match_sets", MatchSet),
            ("match_stats", MatchStats),
            ("match_events", MatchEvent),
            ("head_to_heads", HeadToHead),
            ("ranking_snapshots", RankingSnapshot),
            ("news_categories", NewsCategory),
            ("tags", Tag),
            ("news_articles", NewsArticle),
            ("favorite_entities", FavoriteEntity),
            ("notification_subscriptions", NotificationSubscription),
            ("notifications", Notification),
            ("audit_logs", AuditLog),
        ]
        for name, model in tables:
            print(f"{name}: {await _count(session, model)}")
    await db_session_manager.dispose()


if __name__ == "__main__":
    asyncio.run(seed_all_tables())
