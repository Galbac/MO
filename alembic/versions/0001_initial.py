"""initial tennis portal schema"""

from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="user"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("first_name", sa.String(length=120), nullable=True),
        sa.Column("last_name", sa.String(length=120), nullable=True),
        sa.Column("avatar_url", sa.String(length=512), nullable=True),
        sa.Column("locale", sa.String(length=16), nullable=False, server_default="ru"),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="Europe/Moscow"),
        sa.Column("is_email_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_role", "users", ["role"])
    op.create_index("ix_users_status", "users", ["status"])

    op.create_table(
        "players",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("first_name", sa.String(length=120), nullable=False),
        sa.Column("last_name", sa.String(length=120), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("country_code", sa.String(length=8), nullable=False),
        sa.Column("country_name", sa.String(length=120), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("height_cm", sa.Integer(), nullable=True),
        sa.Column("weight_kg", sa.Integer(), nullable=True),
        sa.Column("hand", sa.String(length=32), nullable=True),
        sa.Column("backhand", sa.String(length=32), nullable=True),
        sa.Column("biography", sa.Text(), nullable=True),
        sa.Column("photo_url", sa.String(length=512), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("current_rank", sa.Integer(), nullable=True),
        sa.Column("current_points", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_players_slug", "players", ["slug"], unique=True)
    op.create_index("ix_players_full_name", "players", ["full_name"])
    op.create_index("ix_players_country_code", "players", ["country_code"])
    op.create_index("ix_players_current_rank", "players", ["current_rank"])

    op.create_table(
        "tournaments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("short_name", sa.String(length=128), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("surface", sa.String(length=32), nullable=False),
        sa.Column("indoor", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("country_code", sa.String(length=8), nullable=True),
        sa.Column("prize_money", sa.String(length=120), nullable=True),
        sa.Column("points_winner", sa.Integer(), nullable=True),
        sa.Column("season_year", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="scheduled"),
        sa.Column("logo_url", sa.String(length=512), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_tournaments_slug", "tournaments", ["slug"], unique=True)
    op.create_index("ix_tournaments_category", "tournaments", ["category"])
    op.create_index("ix_tournaments_surface", "tournaments", ["surface"])
    op.create_index("ix_tournaments_season_year", "tournaments", ["season_year"])

    op.create_table(
        "news_categories",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
    )
    op.create_index("ix_news_categories_slug", "news_categories", ["slug"], unique=True)

    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
    )
    op.create_index("ix_tags_slug", "tags", ["slug"], unique=True)

    op.create_table(
        "matches",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("tournament_id", sa.Integer(), sa.ForeignKey("tournaments.id"), nullable=False),
        sa.Column("round_code", sa.String(length=32), nullable=True),
        sa.Column("best_of_sets", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("player1_id", sa.Integer(), sa.ForeignKey("players.id"), nullable=False),
        sa.Column("player2_id", sa.Integer(), sa.ForeignKey("players.id"), nullable=False),
        sa.Column("winner_id", sa.Integer(), sa.ForeignKey("players.id"), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actual_start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("court_name", sa.String(length=120), nullable=True),
        sa.Column("score_summary", sa.String(length=255), nullable=True),
        sa.Column("retire_reason", sa.Text(), nullable=True),
        sa.Column("walkover_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_matches_slug", "matches", ["slug"], unique=True)
    op.create_index("ix_matches_status", "matches", ["status"])
    op.create_index("ix_matches_scheduled_at", "matches", ["scheduled_at"])

    op.create_table(
        "match_sets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("match_id", sa.Integer(), sa.ForeignKey("matches.id"), nullable=False),
        sa.Column("set_number", sa.Integer(), nullable=False),
        sa.Column("player1_games", sa.Integer(), nullable=False),
        sa.Column("player2_games", sa.Integer(), nullable=False),
        sa.Column("tiebreak_player1_points", sa.Integer(), nullable=True),
        sa.Column("tiebreak_player2_points", sa.Integer(), nullable=True),
        sa.Column("is_finished", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_match_sets_match_id", "match_sets", ["match_id"])

    op.create_table(
        "match_stats",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("match_id", sa.Integer(), sa.ForeignKey("matches.id"), nullable=False),
        sa.Column("player1_aces", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("player2_aces", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("player1_double_faults", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("player2_double_faults", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("player1_first_serve_pct", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("player2_first_serve_pct", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("player1_break_points_saved", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("player2_break_points_saved", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_match_stats_match_id", "match_stats", ["match_id"], unique=True)

    op.create_table(
        "match_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("match_id", sa.Integer(), sa.ForeignKey("matches.id"), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("set_number", sa.Integer(), nullable=True),
        sa.Column("game_number", sa.Integer(), nullable=True),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id"), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_match_events_match_id", "match_events", ["match_id"])
    op.create_index("ix_match_events_event_type", "match_events", ["event_type"])

    op.create_table(
        "head_to_heads",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("player1_id", sa.Integer(), sa.ForeignKey("players.id"), nullable=False),
        sa.Column("player2_id", sa.Integer(), sa.ForeignKey("players.id"), nullable=False),
        sa.Column("total_matches", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("player1_wins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("player2_wins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hard_player1_wins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hard_player2_wins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("clay_player1_wins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("clay_player2_wins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("grass_player1_wins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("grass_player2_wins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_match_id", sa.Integer(), sa.ForeignKey("matches.id"), nullable=True),
    )

    op.create_table(
        "ranking_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ranking_type", sa.String(length=32), nullable=False),
        sa.Column("ranking_date", sa.String(length=16), nullable=False),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id"), nullable=False),
        sa.Column("rank_position", sa.Integer(), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("movement", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "news_articles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("subtitle", sa.String(length=255), nullable=True),
        sa.Column("lead", sa.Text(), nullable=True),
        sa.Column("content_html", sa.Text(), nullable=False),
        sa.Column("cover_image_url", sa.String(length=512), nullable=True),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("news_categories.id"), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("seo_title", sa.String(length=255), nullable=True),
        sa.Column("seo_description", sa.String(length=512), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_news_articles_slug", "news_articles", ["slug"], unique=True)
    op.create_index("ix_news_articles_status", "news_articles", ["status"])

    op.create_table(
        "favorite_entities",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
    )

    op.create_table(
        "notification_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("notification_types", sa.JSON(), nullable=False),
        sa.Column("channels", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="unread"),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("before_json", sa.JSON(), nullable=True),
        sa.Column("after_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    for table_name in [
        "audit_logs",
        "notifications",
        "notification_subscriptions",
        "favorite_entities",
        "news_articles",
        "ranking_snapshots",
        "head_to_heads",
        "match_events",
        "match_stats",
        "match_sets",
        "matches",
        "tags",
        "news_categories",
        "tournaments",
        "players",
        "users",
    ]:
        op.drop_table(table_name)
