from datetime import UTC, date, datetime

import base64
import hashlib

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from source.config.settings import settings
from source.db.models import (
    FavoriteEntity,
    HeadToHead,
    Match,
    Notification,
    NotificationSubscription,
    MatchEvent,
    MatchSet,
    MatchStats,
    NewsArticle,
    NewsCategory,
    Player,
    RankingSnapshot,
    Tag,
    Tournament,
    User,
)


def _seed_hash_password(password: str) -> str:
    salt = b"seeded-demo-salt"
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"{base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


async def seed_demo_data(session: AsyncSession) -> None:
    if not settings.db.seed_demo_data:
        return

    existing = await session.scalar(select(Player.id).limit(1))
    if existing is not None:
        return

    now = datetime(2026, 3, 6, 12, 0, tzinfo=UTC)

    admin = User(
        id=1,
        email="admin@example.com",
        username="admin",
        password_hash=_seed_hash_password("AdminPass123"),
        role="admin",
        status="active",
        first_name="Portal",
        last_name="Admin",
        is_email_verified=True,
    )
    user = User(
        id=2,
        email="user@example.com",
        username="demo_user",
        password_hash=_seed_hash_password("UserPass123"),
        role="user",
        status="active",
        first_name="Demo",
        last_name="User",
        is_email_verified=True,
    )

    players = [
        Player(
            id=1,
            slug="novak-djokovic",
            first_name="Novak",
            last_name="Djokovic",
            full_name="Novak Djokovic",
            country_code="SRB",
            country_name="Serbia",
            birth_date=date(1987, 5, 22),
            height_cm=188,
            weight_kg=77,
            hand="right",
            backhand="two-handed",
            biography="24-time Grand Slam champion.",
            photo_url="/media/players/djokovic.jpg",
            status="active",
            current_rank=1,
            current_points=9850,
        ),
        Player(
            id=2,
            slug="jannik-sinner",
            first_name="Jannik",
            last_name="Sinner",
            full_name="Jannik Sinner",
            country_code="ITA",
            country_name="Italy",
            birth_date=date(2001, 8, 16),
            height_cm=191,
            weight_kg=77,
            hand="right",
            backhand="two-handed",
            biography="Aggressive baseliner and major champion contender.",
            photo_url="/media/players/sinner.jpg",
            status="active",
            current_rank=2,
            current_points=8610,
        ),
        Player(
            id=3,
            slug="daniil-medvedev",
            first_name="Daniil",
            last_name="Medvedev",
            full_name="Daniil Medvedev",
            country_code="RUS",
            country_name="Russia",
            birth_date=date(1996, 2, 11),
            height_cm=198,
            weight_kg=83,
            hand="right",
            backhand="two-handed",
            biography="Former world No. 1 with elite hard-court results.",
            photo_url="/media/players/medvedev.jpg",
            status="active",
            current_rank=4,
            current_points=6530,
        ),
        Player(
            id=4,
            slug="andrey-rublev",
            first_name="Andrey",
            last_name="Rublev",
            full_name="Andrey Rublev",
            country_code="RUS",
            country_name="Russia",
            birth_date=date(1997, 10, 20),
            height_cm=188,
            weight_kg=75,
            hand="right",
            backhand="two-handed",
            biography="Top-10 regular with heavy forehand.",
            photo_url="/media/players/rublev.jpg",
            status="active",
            current_rank=6,
            current_points=5120,
        ),
    ]

    tournaments = [
        Tournament(
            id=1,
            slug="australian-open-2026",
            name="Australian Open 2026",
            short_name="AO 2026",
            category="grand_slam",
            surface="hard",
            indoor=False,
            city="Melbourne",
            country_code="AUS",
            prize_money="$86,500,000",
            points_winner=2000,
            season_year=2026,
            start_date=date(2026, 1, 12),
            end_date=date(2026, 1, 26),
            status="finished",
            logo_url="/media/tournaments/ao.png",
            description="First Grand Slam of the season.",
        ),
        Tournament(
            id=2,
            slug="indian-wells-2026",
            name="Indian Wells 2026",
            short_name="Indian Wells",
            category="masters_1000",
            surface="hard",
            indoor=False,
            city="Indian Wells",
            country_code="USA",
            prize_money="$9,200,000",
            points_winner=1000,
            season_year=2026,
            start_date=date(2026, 3, 5),
            end_date=date(2026, 3, 16),
            status="live",
            logo_url="/media/tournaments/iw.png",
            description="Premier hard-court event in California.",
        ),
    ]

    matches = [
        Match(
            id=1,
            slug="djokovic-vs-sinner-ao-2026-final",
            tournament_id=1,
            round_code="F",
            best_of_sets=5,
            player1_id=1,
            player2_id=2,
            winner_id=1,
            status="finished",
            scheduled_at=datetime(2026, 1, 26, 10, 30, tzinfo=UTC),
            actual_start_at=datetime(2026, 1, 26, 10, 35, tzinfo=UTC),
            actual_end_at=datetime(2026, 1, 26, 13, 51, tzinfo=UTC),
            court_name="Rod Laver Arena",
            score_summary="6-4 3-6 7-5 6-3",
        ),
        Match(
            id=2,
            slug="medvedev-vs-rublev-indian-wells-2026-sf",
            tournament_id=2,
            round_code="SF",
            best_of_sets=3,
            player1_id=3,
            player2_id=4,
            winner_id=None,
            status="live",
            scheduled_at=datetime(2026, 3, 6, 19, 0, tzinfo=UTC),
            actual_start_at=datetime(2026, 3, 6, 19, 3, tzinfo=UTC),
            actual_end_at=None,
            court_name="Stadium 1",
            score_summary="6-4 4-6 3-2",
        ),
    ]

    session.add_all([admin, user, *players, *tournaments, *matches])
    session.add_all([
        MatchSet(id=1, match_id=1, set_number=1, player1_games=6, player2_games=4, is_finished=True),
        MatchSet(id=2, match_id=1, set_number=2, player1_games=3, player2_games=6, is_finished=True),
        MatchSet(id=3, match_id=1, set_number=3, player1_games=7, player2_games=5, is_finished=True),
        MatchSet(id=4, match_id=1, set_number=4, player1_games=6, player2_games=3, is_finished=True),
        MatchSet(id=5, match_id=2, set_number=1, player1_games=6, player2_games=4, is_finished=True),
        MatchSet(id=6, match_id=2, set_number=2, player1_games=4, player2_games=6, is_finished=True),
        MatchSet(id=7, match_id=2, set_number=3, player1_games=3, player2_games=2, is_finished=False),
        MatchStats(id=1, match_id=1, player1_aces=9, player2_aces=14, player1_double_faults=2, player2_double_faults=4, player1_first_serve_pct=68.0, player2_first_serve_pct=61.0, player1_break_points_saved=7, player2_break_points_saved=4, duration_minutes=196),
        MatchStats(id=2, match_id=2, player1_aces=11, player2_aces=7, player1_double_faults=1, player2_double_faults=3, player1_first_serve_pct=72.0, player2_first_serve_pct=64.0, player1_break_points_saved=3, player2_break_points_saved=2, duration_minutes=128),
        MatchEvent(id=1, match_id=1, event_type="set_finished", set_number=1, game_number=10, player_id=1, payload_json={"score": "6-4"}, created_at=datetime(2026, 1, 26, 11, 20, tzinfo=UTC)),
        MatchEvent(id=2, match_id=1, event_type="match_finished", set_number=4, game_number=9, player_id=1, payload_json={"score": "6-4 3-6 7-5 6-3"}, created_at=datetime(2026, 1, 26, 13, 51, tzinfo=UTC)),
        MatchEvent(id=3, match_id=2, event_type="break_point", set_number=3, game_number=5, player_id=3, payload_json={"converted": True}, created_at=now),
        HeadToHead(id=1, player1_id=1, player2_id=2, total_matches=5, player1_wins=3, player2_wins=2, hard_player1_wins=3, hard_player2_wins=2, clay_player1_wins=0, clay_player2_wins=0, grass_player1_wins=0, grass_player2_wins=0, last_match_id=1),
        RankingSnapshot(id=1, ranking_type="atp", ranking_date="2026-02-16", player_id=1, rank_position=2, points=9410, movement=1),
        RankingSnapshot(id=2, ranking_type="atp", ranking_date="2026-03-02", player_id=1, rank_position=1, points=9850, movement=1),
        RankingSnapshot(id=3, ranking_type="atp", ranking_date="2026-03-02", player_id=2, rank_position=2, points=8610, movement=0),
        RankingSnapshot(id=4, ranking_type="atp", ranking_date="2026-03-02", player_id=3, rank_position=4, points=6530, movement=1),
        RankingSnapshot(id=5, ranking_type="atp", ranking_date="2026-03-02", player_id=4, rank_position=6, points=5120, movement=-1),
        NewsCategory(id=1, slug="analysis", name="Analysis"),
        Tag(id=1, slug="djokovic", name="Djokovic"),
        Tag(id=2, slug="indian-wells", name="Indian Wells"),
        NewsArticle(id=1, slug="djokovic-wins-ao-2026", title="Djokovic wins Australian Open 2026", subtitle="Veteran outlasts Sinner in four sets", lead="Djokovic claimed another major title after a high-level final.", content_html="<p>Novak Djokovic defeated Jannik Sinner in four sets to lift the Australian Open trophy.</p>", cover_image_url="/media/news/djokovic-ao.jpg", author_id=1, category_id=1, status="published", seo_title="Djokovic wins AO 2026", seo_description="Grand Slam final recap and key tactical points.", published_at=now),
        NewsArticle(id=2, slug="medvedev-rublev-live-updates", title="Medvedev vs Rublev live updates", subtitle="Indian Wells semifinal in progress", lead="Momentum swings continue in California.", content_html="<p>Follow the semifinal live with score changes and match stats.</p>", cover_image_url="/media/news/live-iw.jpg", author_id=1, category_id=1, status="published", seo_title="Indian Wells semifinal live", seo_description="Live score and tactical context from Medvedev vs Rublev.", published_at=now),
        FavoriteEntity(id=1, user_id=2, entity_type="player", entity_id=1),
        FavoriteEntity(id=2, user_id=2, entity_type="tournament", entity_id=1),
        NotificationSubscription(id=1, user_id=2, entity_type="player", entity_id=1, notification_types=["match_start", "ranking_change"], channels=["web", "email"], is_active=True),
        Notification(id=1, user_id=2, type="match_start", title="Djokovic match starts soon", body="Australian Open final starts in 15 minutes.", payload_json={"entity_type": "match", "entity_id": 1}, status="unread", read_at=None),
        Notification(id=2, user_id=2, type="news", title="New feature story published", body="Read the latest Australian Open final analysis.", payload_json={"entity_type": "news", "entity_id": 1}, status="read", read_at=now),
    ])
    await session.commit()
