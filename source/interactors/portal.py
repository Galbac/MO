from datetime import UTC, datetime

from fastapi import HTTPException, status

from source.config.settings import settings
from source.schemas.pydantic.admin import (
    AdminIntegrationItem,
    AdminNotificationBroadcast,
    AdminNotificationTemplate,
    AdminUserItem,
    AuditLogItem,
)
from source.schemas.pydantic.auth import (
    AuthResponse,
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshTokenRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SimpleMessage,
    VerifyEmailRequest,
)
from source.schemas.pydantic.common import PaginatedResponse, PaginationMeta, SuccessResponse
from source.schemas.pydantic.match import (
    MatchDetail,
    MatchEventCreateRequest,
    MatchEventItem,
    MatchPreview,
    MatchScore,
    MatchScoreUpdateRequest,
    MatchStats,
    MatchStatsUpdateRequest,
    MatchStatusUpdateRequest,
    MatchSummary,
)
from source.schemas.pydantic.media import MediaFile
from source.schemas.pydantic.news import (
    NewsArticleCreateRequest,
    NewsArticleDetail,
    NewsArticleSummary,
    NewsCategoryItem,
    NewsStatusRequest,
    TagItem,
)
from source.schemas.pydantic.notification import NotificationItem, NotificationUnreadCount
from source.schemas.pydantic.player import (
    H2HResponse,
    PlayerComparison,
    PlayerDetail,
    PlayerNewsItem,
    PlayerStats,
    PlayerSummary,
    RankingHistoryPoint,
    SeoMeta,
    TitleItem,
    UpcomingMatchItem,
)
from source.schemas.pydantic.ranking import RankingEntry, RankingImportJob, RankingSnapshotItem
from source.schemas.pydantic.search import SearchResults, SearchSuggestion
from source.schemas.pydantic.tournament import ChampionItem, DrawMatchItem, TournamentDetail, TournamentSummary
from source.schemas.pydantic.user import (
    FavoriteCreateRequest,
    FavoriteItem,
    NotificationSubscriptionCreateRequest,
    NotificationSubscriptionItem,
    NotificationSubscriptionUpdateRequest,
    UserPasswordChangeRequest,
    UserProfile,
    UserTokenBundle,
    UserUpdateRequest,
)


class PortalInteractor:
    def __init__(self) -> None:
        self._now = datetime(2026, 3, 6, 12, 0, tzinfo=UTC)

    def _user(self) -> UserProfile:
        return UserProfile(
            id=1,
            email=settings.demo.user_email,
            username="demo_user",
            role="user",
            status="active",
            first_name="Демо",
            last_name="Пользователь",
            avatar_url="/media/avatars/demo.png",
            locale="ru",
            timezone="Europe/Moscow",
            is_email_verified=True,
            created_at=self._now,
            updated_at=self._now,
        )

    def _players(self) -> list[PlayerDetail]:
        return [
            PlayerDetail(
                id=1,
                slug="novak-djokovic",
                first_name="Novak",
                last_name="Djokovic",
                full_name="Novak Djokovic",
                country_code="SRB",
                country_name="Serbia",
                current_rank=1,
                current_points=9850,
                photo_url="/media/players/djokovic.jpg",
                biography="24-кратный чемпион турниров Большого шлема.",
                hand="right",
                backhand="two-handed",
                status="active",
                stats=PlayerStats(
                    season=2026,
                    matches_played=18,
                    wins=16,
                    losses=2,
                    win_rate=88.9,
                    hard_record="14-1",
                    clay_record="0-0",
                    grass_record="0-0",
                ),
                form=["W", "W", "W", "L", "W"],
                ranking_history=[
                    RankingHistoryPoint(ranking_date="2026-02-16", rank_position=2, points=9410, movement=1),
                    RankingHistoryPoint(ranking_date="2026-03-02", rank_position=1, points=9850, movement=1),
                ],
                titles=[TitleItem(tournament_name="Australian Open", season_year=2026, surface="hard", category="grand_slam")],
                seo=SeoMeta(
                    title="Профиль Новака Джоковича",
                    description="Статистика, динамика рейтинга и последние матчи Новака Джоковича.",
                    canonical_url="/players/novak-djokovic",
                ),
            ),
            PlayerDetail(
                id=2,
                slug="jannik-sinner",
                first_name="Jannik",
                last_name="Sinner",
                full_name="Jannik Sinner",
                country_code="ITA",
                country_name="Italy",
                current_rank=2,
                current_points=8710,
                photo_url="/media/players/sinner.jpg",
                biography="Агрессивный игрок задней линии.",
                hand="right",
                backhand="two-handed",
                status="active",
                stats=PlayerStats(
                    season=2026,
                    matches_played=19,
                    wins=17,
                    losses=2,
                    win_rate=89.5,
                    hard_record="15-2",
                    clay_record="0-0",
                    grass_record="0-0",
                ),
                form=["W", "W", "L", "W", "W"],
                ranking_history=[
                    RankingHistoryPoint(ranking_date="2026-02-16", rank_position=1, points=9060, movement=-1),
                    RankingHistoryPoint(ranking_date="2026-03-02", rank_position=2, points=8710, movement=-1),
                ],
                titles=[TitleItem(tournament_name="Rotterdam Open", season_year=2026, surface="hard", category="atp_500")],
                seo=SeoMeta(
                    title="Профиль Янника Синнера",
                    description="Статистика, динамика рейтинга и последние матчи Янника Синнера.",
                    canonical_url="/players/jannik-sinner",
                ),
            ),
        ]

    def _tournaments(self) -> list[TournamentDetail]:
        return [
            TournamentDetail(
                id=1,
                slug="australian-open-2026",
                name="Australian Open",
                short_name="AO",
                category="grand_slam",
                surface="hard",
                season_year=2026,
                start_date="2026-01-12",
                end_date="2026-01-26",
                status="finished",
                city="Melbourne",
                country_code="AU",
                prize_money="$86,500,000",
                points_winner=2000,
                description="Турнир Большого шлема в Мельбурн Парке.",
                champions=[ChampionItem(season_year=2026, player_name="Novak Djokovic")],
                draw=[DrawMatchItem(round_code="F", player1_name="Novak Djokovic", player2_name="Jannik Sinner", score_summary="6-4 3-6 7-5 6-3")],
                participants=[player.model_dump() for player in self._players()],
                current_matches=[],
                seo={"title": "Australian Open 2026", "description": "Сетка, результаты, участники и чемпионы."},
            ),
        ]

    def _match_events(self) -> list[MatchEventItem]:
        return [
            MatchEventItem(
                id=1,
                event_type="set_finished",
                set_number=1,
                game_number=10,
                player_id=1,
                payload_json={"score": "6-4"},
                created_at=self._now,
            ),
            MatchEventItem(
                id=2,
                event_type="break_point",
                set_number=3,
                game_number=11,
                player_id=1,
                payload_json={"converted": True},
                created_at=self._now,
            ),
        ]

    def _matches(self) -> list[MatchDetail]:
        return [
            MatchDetail(
                id=1,
                slug="djokovic-vs-sinner-ao-2026-final",
                status="finished",
                scheduled_at=self._now,
                actual_start_at=self._now,
                actual_end_at=self._now,
                player1_id=1,
                player2_id=2,
                player1_name="Novak Djokovic",
                player2_name="Jannik Sinner",
                tournament_id=1,
                tournament_name="Australian Open",
                round_code="F",
                court_name="Rod Laver Arena",
                score_summary="6-4 3-6 7-5 6-3",
                best_of_sets=5,
                winner_id=1,
                score=MatchScore(sets=["6-4", "3-6", "7-5", "6-3"], current_game=None, serving_player_id=1),
                sets=[
                    {"set_number": 1, "player1_games": 6, "player2_games": 4, "is_finished": True},
                    {"set_number": 2, "player1_games": 3, "player2_games": 6, "is_finished": True},
                    {"set_number": 3, "player1_games": 7, "player2_games": 5, "is_finished": True},
                    {"set_number": 4, "player1_games": 6, "player2_games": 3, "is_finished": True},
                ],
                stats=MatchStats(
                    player1_aces=11,
                    player2_aces=15,
                    player1_double_faults=2,
                    player2_double_faults=4,
                    player1_first_serve_pct=67,
                    player2_first_serve_pct=63,
                    player1_break_points_saved=8,
                    player2_break_points_saved=6,
                    duration_minutes=196,
                ),
                timeline=self._match_events(),
                h2h=self._h2h().model_dump(),
                related_news=self._news()[:1],
            ),
            MatchDetail(
                id=2,
                slug="medvedev-vs-rublev-indian-wells-2026-sf",
                status="live",
                scheduled_at=self._now,
                actual_start_at=self._now,
                player1_id=3,
                player2_id=4,
                player1_name="Daniil Medvedev",
                player2_name="Andrey Rublev",
                tournament_id=2,
                tournament_name="Indian Wells",
                round_code="SF",
                court_name="Stadium 1",
                score_summary="6-4 2-3",
                best_of_sets=3,
                winner_id=None,
                score=MatchScore(sets=["6-4", "2-3"], current_game="30-15", serving_player_id=3),
                sets=[
                    {"set_number": 1, "player1_games": 6, "player2_games": 4, "is_finished": True},
                    {"set_number": 2, "player1_games": 2, "player2_games": 3, "is_finished": False},
                ],
                stats=MatchStats(duration_minutes=76),
                timeline=self._match_events(),
                h2h={},
                related_news=[],
            ),
        ]

    def _categories(self) -> list[NewsCategoryItem]:
        return [
            NewsCategoryItem(id=1, slug="grand-slams", name="Grand Slams"),
            NewsCategoryItem(id=2, slug="rankings", name="Rankings"),
        ]

    def _tags(self) -> list[TagItem]:
        return [
            TagItem(id=1, slug="djokovic", name="Djokovic"),
            TagItem(id=2, slug="australian-open", name="Australian Open"),
        ]

    def _news(self) -> list[NewsArticleDetail]:
        category = self._categories()[0]
        tags = self._tags()
        return [
            NewsArticleDetail(
                id=1,
                slug="ao-final-preview",
                title="Превью финала AO",
                subtitle="Джокович против Синнера",
                lead="Подробный разбор финала Australian Open.",
                cover_image_url="/media/news/ao-final.jpg",
                status="published",
                published_at="2026-01-25T09:00:00Z",
                category=category,
                tags=tags,
                content_html="<p>Редакционный материал о финале Australian Open.</p>",
                seo_title="Превью финала AO",
                seo_description="Превью финала Australian Open 2026 года.",
            ),
            NewsArticleDetail(
                id=2,
                slug="rankings-shake-up",
                title="Перестановки в рейтинге после Мельбурна",
                lead="Изменения в первой десятке ATP после мэйджора.",
                status="published",
                published_at="2026-01-27T09:00:00Z",
                category=self._categories()[1],
                tags=[tags[0]],
                content_html="<p>Итоги изменений в рейтинге ATP после мэйджора.</p>",
                seo_title="Обновление рейтинга ATP",
                seo_description="Изменения в рейтинге ATP после турнира Большого шлема.",
            ),
        ]

    def _rankings(self) -> list[RankingEntry]:
        return [
            RankingEntry(position=1, player_id=1, player_name="Novak Djokovic", country_code="SRB", points=9850, movement=1),
            RankingEntry(position=2, player_id=2, player_name="Jannik Sinner", country_code="ITA", points=8710, movement=-1),
        ]

    def _notifications(self) -> list[NotificationItem]:
        return [
            NotificationItem(
                id=1,
                type="match_start",
                title="Матч скоро начнется",
                body="Джокович против Синнера начнется через 15 минут",
                payload_json={"match_id": 1},
                created_at=self._now,
            ),
            NotificationItem(
                id=2,
                type="news",
                title="Опубликован новый материал",
                body="Превью финала AO уже доступно",
                payload_json={"slug": "ao-final-preview"},
                created_at=self._now,
            ),
        ]

    def _favorites(self) -> list[FavoriteItem]:
        return [
            FavoriteItem(id=1, user_id=1, entity_type="player", entity_id=1, entity_name="Novak Djokovic"),
            FavoriteItem(id=2, user_id=1, entity_type="tournament", entity_id=1, entity_name="Australian Open"),
        ]

    def _subscriptions(self) -> list[NotificationSubscriptionItem]:
        return [
            NotificationSubscriptionItem(
                id=1,
                user_id=1,
                entity_type="player",
                entity_id=1,
                notification_types=["match_start", "ranking_change"],
                channels=["site", "email"],
                is_active=True,
            ),
        ]

    def _admin_users(self) -> list[AdminUserItem]:
        return [
            AdminUserItem(
                id=1,
                email=settings.demo.admin_email,
                username="admin",
                role="admin",
                status="active",
                created_at=self._now,
            ),
            AdminUserItem(
                id=2,
                email=settings.demo.editor_email,
                username="editor",
                role="editor",
                status="active",
                created_at=self._now,
            ),
        ]

    def _audit_logs(self) -> list[AuditLogItem]:
        return [
            AuditLogItem(
                id=1,
                action="publish_news",
                entity_type="news_article",
                entity_id=1,
                before_json={"status": "review"},
                after_json={"status": "published"},
                created_at=self._now,
            ),
            AuditLogItem(
                id=2,
                action="finalize_match",
                entity_type="match",
                entity_id=1,
                before_json={"status": "live"},
                after_json={"status": "finished"},
                created_at=self._now,
            ),
        ]

    def _integrations(self) -> list[AdminIntegrationItem]:
        return [
            AdminIntegrationItem(provider="live_score_provider", status="healthy", last_sync_at=self._now),
            AdminIntegrationItem(provider="rankings_provider", status="healthy", last_sync_at=self._now),
        ]

    def _h2h(self) -> H2HResponse:
        return H2HResponse(
            player1_id=1,
            player2_id=2,
            total_matches=5,
            player1_wins=3,
            player2_wins=2,
            hard_player1_wins=3,
            hard_player2_wins=2,
            clay_player1_wins=0,
            clay_player2_wins=0,
            grass_player1_wins=0,
            grass_player2_wins=0,
            last_match_id=1,
        )

    @staticmethod
    def _paginate[T](items: list[T], page: int, per_page: int) -> tuple[list[T], PaginationMeta]:
        start = (page - 1) * per_page
        end = start + per_page
        return items[start:end], PaginationMeta.build(page=page, per_page=per_page, total=len(items))

    @staticmethod
    def _get_by_id[T](items: list[T], entity_id: int, entity_name: str) -> T:
        for item in items:
            if getattr(item, "id", None) == entity_id:
                return item
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{entity_name} not found")

    @staticmethod
    def _get_by_slug[T](items: list[T], slug: str, entity_name: str) -> T:
        for item in items:
            if getattr(item, "slug", None) == slug:
                return item
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{entity_name} not found")

    def register_user(self, payload: RegisterRequest) -> AuthResponse:
        user = self._user().model_copy(update={"email": payload.email, "username": payload.username})
        return AuthResponse(data=UserTokenBundle(access_token="access-token", refresh_token="refresh-token", user=user))

    def login_user(self, _: LoginRequest) -> AuthResponse:
        return AuthResponse(data=UserTokenBundle(access_token="access-token", refresh_token="refresh-token", user=self._user()))

    def refresh_token(self, _: RefreshTokenRequest) -> AuthResponse:
        return AuthResponse(data=UserTokenBundle(access_token="new-access-token", refresh_token="refresh-token", user=self._user()))

    def logout_user(self, _: LogoutRequest) -> MessageResponse:
        return MessageResponse(data=SimpleMessage(message="Logged out"))

    def forgot_password(self, _: ForgotPasswordRequest) -> MessageResponse:
        return MessageResponse(data=SimpleMessage(message="Reset email queued"))

    def reset_password(self, _: ResetPasswordRequest) -> MessageResponse:
        return MessageResponse(data=SimpleMessage(message="Password updated"))

    def verify_email(self, _: VerifyEmailRequest) -> MessageResponse:
        return MessageResponse(data=SimpleMessage(message="Email verified"))

    def get_auth_me(self) -> SuccessResponse[UserProfile]:
        return SuccessResponse(data=self._user())

    def get_current_user(self) -> SuccessResponse[UserProfile]:
        return SuccessResponse(data=self._user())

    def update_current_user(self, payload: UserUpdateRequest) -> SuccessResponse[UserProfile]:
        current = self._user()
        return SuccessResponse(data=current.model_copy(update=payload.model_dump(exclude_none=True)))

    def change_password(self, _: UserPasswordChangeRequest) -> MessageResponse:
        return MessageResponse(data=SimpleMessage(message="Password changed and tokens revoked"))

    def list_favorites(self) -> SuccessResponse[list[FavoriteItem]]:
        return SuccessResponse(data=self._favorites())

    def create_favorite(self, payload: FavoriteCreateRequest) -> SuccessResponse[FavoriteItem]:
        return SuccessResponse(
            data=FavoriteItem(
                id=99,
                user_id=1,
                entity_type=payload.entity_type,
                entity_id=payload.entity_id,
                entity_name=f"{payload.entity_type}:{payload.entity_id}",
            )
        )

    def delete_favorite(self, favorite_id: int) -> MessageResponse:
        self._get_by_id(self._favorites(), favorite_id, "Favorite")
        return MessageResponse(data=SimpleMessage(message="Favorite deleted"))

    def list_subscriptions(self) -> SuccessResponse[list[NotificationSubscriptionItem]]:
        return SuccessResponse(data=self._subscriptions())

    def create_subscription(
        self,
        payload: NotificationSubscriptionCreateRequest,
    ) -> SuccessResponse[NotificationSubscriptionItem]:
        return SuccessResponse(
            data=NotificationSubscriptionItem(
                id=99,
                user_id=1,
                entity_type=payload.entity_type,
                entity_id=payload.entity_id,
                notification_types=payload.notification_types,
                channels=payload.channels,
                is_active=True,
            )
        )

    def update_subscription(
        self,
        subscription_id: int,
        payload: NotificationSubscriptionUpdateRequest,
    ) -> SuccessResponse[NotificationSubscriptionItem]:
        subscription = self._get_by_id(self._subscriptions(), subscription_id, "Subscription")
        return SuccessResponse(data=subscription.model_copy(update=payload.model_dump(exclude_none=True)))

    def delete_subscription(self, subscription_id: int) -> MessageResponse:
        self._get_by_id(self._subscriptions(), subscription_id, "Subscription")
        return MessageResponse(data=SimpleMessage(message="Subscription deleted"))

    def list_user_notifications(self) -> SuccessResponse[list[NotificationItem]]:
        return SuccessResponse(data=self._notifications())

    def mark_notification_read(self, notification_id: int) -> SuccessResponse[NotificationItem]:
        notification = self._get_by_id(self._notifications(), notification_id, "Notification")
        return SuccessResponse(data=notification.model_copy(update={"status": "read", "read_at": self._now}))

    def read_all_notifications(self) -> MessageResponse:
        return MessageResponse(data=SimpleMessage(message="All notifications marked as read"))

    def list_players(
        self,
        search: str | None = None,
        country_code: str | None = None,
        hand: str | None = None,
        status_filter: str | None = None,
        rank_from: int | None = None,
        rank_to: int | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> PaginatedResponse[PlayerSummary]:
        items = self._players()
        if search:
            items = [item for item in items if search.lower() in item.full_name.lower()]
        if country_code:
            items = [item for item in items if item.country_code == country_code.upper()]
        if hand:
            items = [item for item in items if item.hand == hand]
        if status_filter:
            items = [item for item in items if item.status == status_filter]
        if rank_from is not None:
            items = [item for item in items if item.current_rank and item.current_rank >= rank_from]
        if rank_to is not None:
            items = [item for item in items if item.current_rank and item.current_rank <= rank_to]
        paged, meta = self._paginate([PlayerSummary(**item.model_dump()) for item in items], page, per_page)
        return PaginatedResponse(data=paged, meta=meta)

    def get_player(self, player_id: int) -> SuccessResponse[PlayerDetail]:
        player = self._get_by_id(self._players(), player_id, "Player")
        return SuccessResponse(
            data=player.model_copy(
                update={
                    "recent_matches": [match.model_dump() for match in self._matches() if player_id in {match.player1_id, match.player2_id}],
                    "upcoming_match": UpcomingMatchItem(
                        match_id=2,
                        slug="medvedev-vs-rublev-indian-wells-2026-sf",
                        tournament_name="Indian Wells",
                        opponent_name="Andrey Rublev",
                        scheduled_at="2026-03-06T12:00:00Z",
                        status="live",
                    )
                    if player_id == 1
                    else None,
                }
            )
        )

    def get_player_stats(self, player_id: int) -> SuccessResponse[PlayerStats]:
        return SuccessResponse(data=self.get_player(player_id).data.stats)

    def get_player_matches(self, player_id: int, page: int = 1, per_page: int = 20) -> PaginatedResponse[MatchSummary]:
        items = [match for match in self._matches() if player_id in {match.player1_id, match.player2_id}]
        paged, meta = self._paginate([MatchSummary(**item.model_dump()) for item in items], page, per_page)
        return PaginatedResponse(data=paged, meta=meta)

    def get_player_ranking_history(self, player_id: int) -> SuccessResponse[list[RankingHistoryPoint]]:
        return SuccessResponse(data=self.get_player(player_id).data.ranking_history)

    def get_player_titles(self, player_id: int) -> SuccessResponse[list[TitleItem]]:
        return SuccessResponse(data=self.get_player(player_id).data.titles)

    def get_player_news(self, _: int) -> SuccessResponse[list[PlayerNewsItem]]:
        items = [PlayerNewsItem(id=item.id, slug=item.slug, title=item.title, published_at=item.published_at) for item in self._news()]
        return SuccessResponse(data=items)

    def get_player_upcoming_matches(self, player_id: int) -> SuccessResponse[list[UpcomingMatchItem]]:
        player = self.get_player(player_id).data
        return SuccessResponse(data=[player.upcoming_match] if player and player.upcoming_match else [])

    def compare_players(self, player1_id: int, player2_id: int) -> SuccessResponse[PlayerComparison]:
        player1 = self.get_player(player1_id).data
        player2 = self.get_player(player2_id).data
        assert player1 is not None and player2 is not None
        return SuccessResponse(
            data=PlayerComparison(
                player1=player1,
                player2=player2,
                h2h=self._h2h().model_dump(),
                comparison={
                    "rank_gap": abs((player1.current_rank or 0) - (player2.current_rank or 0)),
                    "surface_edge": "hard",
                },
            )
        )

    def get_h2h(self, player1_id: int, player2_id: int) -> SuccessResponse[H2HResponse]:
        self.get_player(player1_id)
        self.get_player(player2_id)
        return SuccessResponse(data=self._h2h())

    def list_tournaments(self, page: int = 1, per_page: int = 20) -> PaginatedResponse[TournamentSummary]:
        paged, meta = self._paginate([TournamentSummary(**item.model_dump()) for item in self._tournaments()], page, per_page)
        return PaginatedResponse(data=paged, meta=meta)

    def get_tournament(self, tournament_id: int) -> SuccessResponse[TournamentDetail]:
        return SuccessResponse(data=self._get_by_id(self._tournaments(), tournament_id, "Tournament"))

    def get_tournament_matches(self, _: int) -> SuccessResponse[list[MatchSummary]]:
        return SuccessResponse(data=[MatchSummary(**item.model_dump()) for item in self._matches()])

    def get_tournament_draw(self, tournament_id: int) -> SuccessResponse[list[DrawMatchItem]]:
        return SuccessResponse(data=self.get_tournament(tournament_id).data.draw)

    def get_tournament_players(self, _: int) -> SuccessResponse[list[PlayerSummary]]:
        return SuccessResponse(data=[PlayerSummary(**item.model_dump()) for item in self._players()])

    def get_tournament_champions(self, tournament_id: int) -> SuccessResponse[list[ChampionItem]]:
        return SuccessResponse(data=self.get_tournament(tournament_id).data.champions)

    def get_tournament_news(self, _: int) -> SuccessResponse[list[NewsArticleSummary]]:
        return SuccessResponse(data=[NewsArticleSummary(**item.model_dump(exclude={"content_html", "related_news", "seo_title", "seo_description"})) for item in self._news()])

    def get_tournament_calendar(self) -> SuccessResponse[list[TournamentSummary]]:
        return SuccessResponse(data=[TournamentSummary(**item.model_dump()) for item in self._tournaments()])

    def list_matches(self, page: int = 1, per_page: int = 20, status_filter: str | None = None) -> PaginatedResponse[MatchSummary]:
        items = self._matches()
        if status_filter:
            items = [item for item in items if item.status == status_filter]
        paged, meta = self._paginate([MatchSummary(**item.model_dump()) for item in items], page, per_page)
        return PaginatedResponse(data=paged, meta=meta)

    def get_match(self, match_id: int) -> SuccessResponse[MatchDetail]:
        return SuccessResponse(data=self._get_by_id(self._matches(), match_id, "Match"))

    def get_match_score(self, match_id: int) -> SuccessResponse[MatchScore]:
        return SuccessResponse(data=self.get_match(match_id).data.score)

    def get_match_stats(self, match_id: int) -> SuccessResponse[MatchStats]:
        return SuccessResponse(data=self.get_match(match_id).data.stats)

    def get_match_timeline(self, match_id: int) -> SuccessResponse[list[MatchEventItem]]:
        return SuccessResponse(data=self.get_match(match_id).data.timeline)

    def get_match_h2h(self, match_id: int) -> SuccessResponse[H2HResponse]:
        self.get_match(match_id)
        return SuccessResponse(data=self._h2h())

    def get_match_preview(self, match_id: int) -> SuccessResponse[MatchPreview]:
        match = self.get_match(match_id).data
        return SuccessResponse(
            data=MatchPreview(
                h2h_summary=self._h2h().model_dump(),
                player1_form=["W", "W", "W", "L", "W"],
                player2_form=["W", "W", "L", "W", "W"],
                notes=[f"{match.player1_name} has won 3 of the last 5 H2H matches."],
            )
        )

    def get_match_point_by_point(self, match_id: int) -> SuccessResponse[list[MatchEventItem]]:
        return self.get_match_timeline(match_id)

    def get_upcoming_matches(self) -> SuccessResponse[list[MatchSummary]]:
        return SuccessResponse(data=[MatchSummary(**item.model_dump()) for item in self._matches() if item.status in {"scheduled", "live"}])

    def get_match_results(self) -> SuccessResponse[list[MatchSummary]]:
        return SuccessResponse(data=[MatchSummary(**item.model_dump()) for item in self._matches() if item.status == "finished"])

    def list_live_matches(self) -> SuccessResponse[list[MatchSummary]]:
        items = [MatchSummary(**item.model_dump()) for item in self._matches() if item.status in {"live", "scheduled", "about_to_start"}]
        return SuccessResponse(data=items)

    def get_live_match(self, match_id: int) -> SuccessResponse[MatchDetail]:
        return self.get_match(match_id)

    def get_live_feed(self) -> SuccessResponse[list[MatchEventItem]]:
        return SuccessResponse(data=self._match_events())

    def get_rankings(self) -> PaginatedResponse[RankingEntry]:
        items = self._rankings()
        _, meta = self._paginate(items, 1, len(items))
        return PaginatedResponse(data=items, meta=meta)

    def get_current_rankings(self) -> SuccessResponse[list[RankingEntry]]:
        return SuccessResponse(data=self._rankings())

    def get_rankings_history(self, ranking_type: str) -> SuccessResponse[list[RankingSnapshotItem]]:
        return SuccessResponse(data=[RankingSnapshotItem(ranking_type=ranking_type, ranking_date="2026-03-02", entries=self._rankings())])

    def get_player_ranking_snapshots(self, player_id: int) -> SuccessResponse[list[RankingHistoryPoint]]:
        return self.get_player_ranking_history(player_id)

    def get_race_rankings(self) -> SuccessResponse[list[RankingEntry]]:
        return SuccessResponse(data=[entry.model_copy(update={"ranking_type": "race"}) for entry in self._rankings()])

    def list_news(self, page: int = 1, per_page: int = 20) -> PaginatedResponse[NewsArticleSummary]:
        items = [NewsArticleSummary(**item.model_dump(exclude={"content_html", "related_news", "seo_title", "seo_description"})) for item in self._news()]
        paged, meta = self._paginate(items, page, per_page)
        return PaginatedResponse(data=paged, meta=meta)

    def get_news_article(self, slug: str) -> SuccessResponse[NewsArticleDetail]:
        article = self._get_by_slug(self._news(), slug, "Article")
        related = [item for item in self._news() if item.slug != slug][:1]
        return SuccessResponse(data=article.model_copy(update={"related_news": related}))

    def get_news_categories(self) -> SuccessResponse[list[NewsCategoryItem]]:
        return SuccessResponse(data=self._categories())

    def get_news_tags(self) -> SuccessResponse[list[TagItem]]:
        return SuccessResponse(data=self._tags())

    def get_featured_news(self) -> SuccessResponse[list[NewsArticleSummary]]:
        return SuccessResponse(data=self.list_news().data[:1])

    def get_related_news(self, slug: str | None = None) -> SuccessResponse[list[NewsArticleSummary]]:
        items = self.list_news().data
        if slug:
            items = [item for item in items if item.slug != slug]
        return SuccessResponse(data=items[:2])

    def search(self, query: str) -> SuccessResponse[SearchResults]:
        return SuccessResponse(
            data=SearchResults(
                players=self.list_players(search=query).data or [],
                tournaments=self.list_tournaments().data or [],
                matches=self.list_matches().data or [],
                news=self.list_news().data or [],
            )
        )

    def search_suggestions(self, query: str) -> SuccessResponse[list[SearchSuggestion]]:
        return SuccessResponse(data=[SearchSuggestion(text=f"{query} Djokovic", entity_type="player"), SearchSuggestion(text=f"{query} Open", entity_type="tournament")])

    def list_notifications(self) -> SuccessResponse[list[NotificationItem]]:
        return self.list_user_notifications()

    def get_unread_count(self) -> SuccessResponse[NotificationUnreadCount]:
        return SuccessResponse(data=NotificationUnreadCount(unread_count=1))

    def send_test_notification(self) -> MessageResponse:
        return MessageResponse(data=SimpleMessage(message="Test notification sent"))

    def upload_media(self, filename: str, content_type: str | None = None, size: int | None = None) -> SuccessResponse[MediaFile]:
        return SuccessResponse(
            data=MediaFile(
                id=1,
                filename=filename,
                content_type=content_type or "application/octet-stream",
                url=f"/uploads/{filename}",
                size=size,
            )
        )

    def get_media(self, media_id: int) -> SuccessResponse[MediaFile]:
        return SuccessResponse(data=MediaFile(id=media_id, filename="cover.jpg", content_type="image/jpeg", url="/uploads/cover.jpg", size=1024))

    def delete_media(self, _: int) -> MessageResponse:
        return MessageResponse(data=SimpleMessage(message="Media deleted"))

    def list_admin_media(self) -> SuccessResponse[list[MediaFile]]:
        return SuccessResponse(
            data=[
                MediaFile(id=1, filename="cover.jpg", content_type="image/jpeg", url="/uploads/cover.jpg", size=1024),
                MediaFile(id=2, filename="player.jpg", content_type="image/jpeg", url="/uploads/player.jpg", size=2048),
                MediaFile(id=3, filename="draw.pdf", content_type="application/pdf", url="/uploads/draw.pdf", size=4096),
            ]
        )

    def list_admin_users(self) -> SuccessResponse[list[AdminUserItem]]:
        return SuccessResponse(data=self._admin_users())

    def get_admin_user(self, user_id: int) -> SuccessResponse[AdminUserItem]:
        return SuccessResponse(data=self._get_by_id(self._admin_users(), user_id, "User"))

    def update_admin_user(self, user_id: int, payload: dict) -> SuccessResponse[AdminUserItem]:
        user = self._get_by_id(self._admin_users(), user_id, "User")
        return SuccessResponse(data=user.model_copy(update=payload))

    def list_admin_players(self) -> SuccessResponse[list[PlayerSummary]]:
        return SuccessResponse(data=[PlayerSummary(**item.model_dump()) for item in self._players()])

    def create_admin_player(self, payload: dict) -> SuccessResponse[PlayerDetail]:
        return SuccessResponse(data=self._players()[0].model_copy(update=payload))

    def get_admin_player(self, player_id: int) -> SuccessResponse[PlayerDetail]:
        return self.get_player(player_id)

    def update_admin_player(self, player_id: int, payload: dict) -> SuccessResponse[PlayerDetail]:
        return SuccessResponse(data=self.get_player(player_id).data.model_copy(update=payload))

    def delete_admin_player(self, _: int) -> MessageResponse:
        return MessageResponse(data=SimpleMessage(message="Player deleted"))

    def list_admin_tournaments(self) -> SuccessResponse[list[TournamentSummary]]:
        return SuccessResponse(data=[TournamentSummary(**item.model_dump()) for item in self._tournaments()])

    def create_admin_tournament(self, payload: dict) -> SuccessResponse[TournamentDetail]:
        return SuccessResponse(data=self._tournaments()[0].model_copy(update=payload))

    def get_admin_tournament(self, tournament_id: int) -> SuccessResponse[TournamentDetail]:
        return self.get_tournament(tournament_id)

    def update_admin_tournament(self, tournament_id: int, payload: dict) -> SuccessResponse[TournamentDetail]:
        return SuccessResponse(data=self.get_tournament(tournament_id).data.model_copy(update=payload))

    def delete_admin_tournament(self, _: int) -> MessageResponse:
        return MessageResponse(data=SimpleMessage(message="Tournament deleted"))

    def list_admin_matches(self) -> SuccessResponse[list[MatchSummary]]:
        return SuccessResponse(data=[MatchSummary(**item.model_dump()) for item in self._matches()])

    def create_admin_match(self, payload: dict) -> SuccessResponse[MatchDetail]:
        return SuccessResponse(data=self._matches()[0].model_copy(update=payload))

    def get_admin_match(self, match_id: int) -> SuccessResponse[MatchDetail]:
        return self.get_match(match_id)

    def update_admin_match(self, match_id: int, payload: dict) -> SuccessResponse[MatchDetail]:
        return SuccessResponse(data=self.get_match(match_id).data.model_copy(update=payload))

    def delete_admin_match(self, _: int) -> MessageResponse:
        return MessageResponse(data=SimpleMessage(message="Match deleted"))

    def update_admin_match_status(self, match_id: int, payload: MatchStatusUpdateRequest) -> SuccessResponse[MatchDetail]:
        return SuccessResponse(data=self.get_match(match_id).data.model_copy(update={"status": payload.status}))

    def update_admin_match_score(self, match_id: int, payload: MatchScoreUpdateRequest) -> SuccessResponse[MatchDetail]:
        return SuccessResponse(
            data=self.get_match(match_id).data.model_copy(update={"score_summary": payload.score_summary, "sets": payload.sets})
        )

    def update_admin_match_stats(self, match_id: int, payload: MatchStatsUpdateRequest) -> SuccessResponse[MatchDetail]:
        return SuccessResponse(data=self.get_match(match_id).data.model_copy(update={"stats": payload.stats}))

    def create_admin_match_event(self, match_id: int, payload: MatchEventCreateRequest) -> SuccessResponse[MatchEventItem]:
        self.get_match(match_id)
        return SuccessResponse(
            data=MatchEventItem(
                id=99,
                event_type=payload.event_type,
                set_number=payload.set_number,
                game_number=payload.game_number,
                player_id=payload.player_id,
                payload_json=payload.payload_json,
                created_at=self._now,
            )
        )

    def finalize_admin_match(self, match_id: int) -> MessageResponse:
        self.get_match(match_id)
        return MessageResponse(data=SimpleMessage(message="Match finalized and post-processing queued"))

    def reopen_admin_match(self, match_id: int) -> MessageResponse:
        self.get_match(match_id)
        return MessageResponse(data=SimpleMessage(message="Match reopened"))

    def get_admin_ranking_jobs(self) -> SuccessResponse[list[RankingImportJob]]:
        return SuccessResponse(data=[RankingImportJob(id=1, ranking_type="atp", status="finished", imported_at="2026-03-02T08:00:00Z", processed_rows=500)])

    def import_admin_rankings(self) -> MessageResponse:
        return MessageResponse(data=SimpleMessage(message="Ranking import started"))

    def recalculate_ranking_movements(self) -> MessageResponse:
        return MessageResponse(data=SimpleMessage(message="Ranking movements recalculation started"))

    def list_admin_news(self) -> SuccessResponse[list[NewsArticleSummary]]:
        return SuccessResponse(data=self.list_news().data)

    def create_admin_news(self, payload: NewsArticleCreateRequest) -> SuccessResponse[NewsArticleDetail]:
        return SuccessResponse(
            data=NewsArticleDetail(
                id=99,
                slug=payload.slug,
                title=payload.title,
                subtitle=payload.subtitle,
                lead=payload.lead,
                content_html=payload.content_html,
                status=payload.status,
                category=self._categories()[0] if payload.category_id else None,
                tags=[tag for tag in self._tags() if tag.id in payload.tag_ids],
            )
        )

    def get_admin_news(self, news_id: int) -> SuccessResponse[NewsArticleDetail]:
        return SuccessResponse(data=self._get_by_id(self._news(), news_id, "News"))

    def update_admin_news(self, news_id: int, payload: NewsArticleCreateRequest) -> SuccessResponse[NewsArticleDetail]:
        article = self.get_admin_news(news_id).data
        return SuccessResponse(data=article.model_copy(update=payload.model_dump(exclude_none=True)))

    def delete_admin_news(self, _: int) -> MessageResponse:
        return MessageResponse(data=SimpleMessage(message="News deleted"))

    def update_admin_news_status(self, news_id: int, payload: NewsStatusRequest) -> SuccessResponse[NewsArticleDetail]:
        article = self.get_admin_news(news_id).data
        return SuccessResponse(data=article.model_copy(update={"status": payload.status, "published_at": payload.publish_at}))

    def publish_admin_news(self, news_id: int) -> MessageResponse:
        self.get_admin_news(news_id)
        return MessageResponse(data=SimpleMessage(message="News published"))

    def schedule_admin_news(self, news_id: int, payload: NewsStatusRequest) -> MessageResponse:
        self.get_admin_news(news_id)
        return MessageResponse(data=SimpleMessage(message=f"News scheduled for {payload.publish_at or 'later'}"))

    def attach_admin_news_tags(self, _: int) -> SuccessResponse[list[TagItem]]:
        return SuccessResponse(data=self._tags())

    def list_admin_categories(self) -> SuccessResponse[list[NewsCategoryItem]]:
        return SuccessResponse(data=self._categories())

    def list_admin_tags(self) -> SuccessResponse[list[TagItem]]:
        return SuccessResponse(data=self._tags())

    def list_admin_integrations(self) -> SuccessResponse[list[AdminIntegrationItem]]:
        return SuccessResponse(data=self._integrations())

    def sync_admin_integration(self, provider: str) -> MessageResponse:
        return MessageResponse(data=SimpleMessage(message=f"Sync started for {provider}"))

    def get_admin_integration_logs(self, provider: str) -> MessageResponse:
        return MessageResponse(data=SimpleMessage(message=f"Logs collected for {provider}"))

    def list_audit_logs(self) -> SuccessResponse[list[AuditLogItem]]:
        return SuccessResponse(data=self._audit_logs())

    def list_admin_notification_templates(self) -> SuccessResponse[list[AdminNotificationTemplate]]:
        return SuccessResponse(
            data=[
                AdminNotificationTemplate(
                    id=1,
                    code="match_start",
                    title="Match start alert",
                    channel="push",
                    is_active=True,
                    updated_at=self._now,
                ),
                AdminNotificationTemplate(
                    id=2,
                    code="ranking_change",
                    title="Ranking movement digest",
                    channel="email",
                    is_active=True,
                    updated_at=self._now,
                ),
            ]
        )

    def list_admin_notification_history(self) -> SuccessResponse[list[AdminNotificationBroadcast]]:
        return SuccessResponse(
            data=[
                AdminNotificationBroadcast(
                    id=1,
                    title="Оповещения о старте матча Indian Wells",
                    status="sent",
                    sent_count=500,
                    created_at=self._now,
                ),
                AdminNotificationBroadcast(
                    id=2,
                    title="Дайджест изменений рейтинга ATP",
                    status="queued",
                    sent_count=120,
                    created_at=self._now,
                ),
            ]
        )

    def send_admin_test_notification(self) -> MessageResponse:
        return MessageResponse(data=SimpleMessage(message="Тестовое уведомление администратора поставлено в очередь"))


    def get_audit_log(self, log_id: int) -> SuccessResponse[AuditLogItem]:
        return SuccessResponse(data=self._get_by_id(self._audit_logs(), log_id, "Audit log"))


    def get_admin_settings(self) -> SuccessResponse[dict]:
        return SuccessResponse(data={"seo_title": settings.names.title, "support_email": settings.contacts.support_email, "provider_notes": "live_score_provider=enabled"})

    def update_admin_settings(self, payload: dict) -> SuccessResponse[dict]:
        current = self.get_admin_settings().data or {}
        current.update(payload)
        return SuccessResponse(data=current)
