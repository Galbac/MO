import { api } from "/static/js/core/api.js";
import { renderState, renderSkeletonCards } from "/static/js/core/state.js";
import { createLiveSocket } from "/static/js/core/websocket.js";
import {
    debounce,
    escapeHtml,
    extractData,
    extractList,
    formatDate,
    pageName,
    queryParam,
    qs,
    setHtml,
    setText,
    show,
    slugFromPath,
} from "/static/js/core/utils.js";
import { matchCard, newsCard, notificationCard, playerCard, rankingRow, scoreboard, statPair, timelineItem, tournamentCard } from "/static/js/components/renderers.js";

async function resolveEntityId(listRequest, slug) {
    const payload = await listRequest();
    const entity = extractList(payload).find((item) => item.slug === slug);
    return entity?.id || null;
}

function reminderCard(item) {
    return `
        <div class="notification-item">
            <strong>${escapeHtml(item.title || "Матч")}</strong>
            <div class="text-muted small mt-1">${escapeHtml(item.tournament_name || "")}</div>
            <div class="text-muted small mt-1">${escapeHtml(formatDate(item.scheduled_at))}</div>
            <div class="d-flex flex-wrap gap-2 mt-2">
                <span class="badge-soft">${escapeHtml(item.remind_before_minutes || 30)} мин до старта</span>
                <span class="badge-soft">${escapeHtml(item.source === "manual" ? "Мое напоминание" : "Smart tracking")}</span>
            </div>
            ${item.id ? `<div class="d-flex gap-2 mt-3"><button class="btn btn-sm btn-ghost-dark" data-reminder-update="${escapeHtml(item.id)}">Сдвинуть на 60 мин</button><button class="btn btn-sm btn-outline-danger" data-reminder-remove="${escapeHtml(item.id)}">Удалить</button></div>` : ""}
        </div>`;
}

function pushDeviceCard(item) {
    return `
        <div class="notification-item">
            <strong>${escapeHtml(item.device_label || "Браузерное устройство")}</strong>
            <div class="text-muted small mt-1">${escapeHtml(item.permission || "default")}</div>
            <div class="text-muted small mt-1">${escapeHtml(item.endpoint || "")}</div>
            <div class="d-flex gap-2 mt-3">
                <button class="btn btn-sm btn-outline-danger" data-push-remove="${escapeHtml(item.id)}">Удалить</button>
            </div>
        </div>`;
}

function predictionCard(prediction, detail) {
    const favorite = Number(prediction.favorite_player_id) === Number(detail.player1_id) ? detail.player1_name : detail.player2_name;
    return `
        <div class="metric-card">
            <div class="entity-card__eyebrow">Фаворит</div>
            <div class="metric-value">${escapeHtml(favorite || "-")}</div>
            <div class="text-muted mt-2">${escapeHtml(prediction.summary || "")}</div>
            <div class="d-flex flex-wrap gap-2 mt-3">
                <span class="badge-soft">${escapeHtml(Math.round((prediction.player1_probability || 0) * 100))}% / ${escapeHtml(Math.round((prediction.player2_probability || 0) * 100))}%</span>
                <span class="badge-soft">Покрытие: ${escapeHtml(prediction.surface_edge || "-")}</span>
                <span class="badge-soft">Уверенность: ${escapeHtml(prediction.confidence || "medium")}</span>
            </div>
        </div>`;
}

function momentumCard(momentum, detail) {
    return `
        <div class="metric-card">
            <div class="stats-pair">
                <div class="stats-pair__value">${escapeHtml(momentum.player1_pressure || 0)}</div>
                <div class="text-muted small text-center">Давление</div>
                <div class="stats-pair__value is-right">${escapeHtml(momentum.player2_pressure || 0)}</div>
            </div>
            <div class="stats-pair">
                <div class="stats-pair__value">${escapeHtml(momentum.player1_breaks || 0)}</div>
                <div class="text-muted small text-center">Брейки</div>
                <div class="stats-pair__value is-right">${escapeHtml(momentum.player2_breaks || 0)}</div>
            </div>
            <div class="stats-pair">
                <div class="stats-pair__value">${escapeHtml(momentum.player1_service_holds || 0)}</div>
                <div class="text-muted small text-center">Удержания подачи</div>
                <div class="stats-pair__value is-right">${escapeHtml(momentum.player2_service_holds || 0)}</div>
            </div>
            <div class="timeline-list mt-3">
                ${(momentum.recent_points || []).map((point) => `<article class="timeline-item"><div class="timeline-item__time">${escapeHtml(point.event_type)}</div><strong>${escapeHtml(point.label)}</strong><div class="text-muted small mt-2">${escapeHtml(detail.player1_name)} ${escapeHtml(point.player1_score)} : ${escapeHtml(point.player2_score)} ${escapeHtml(detail.player2_name)}</div></article>`).join("") || '<div class="state-card">Momentum появится с live-событиями.</div>'}
            </div>
        </div>`;
}

async function initHome() {
    const [live, rankings, news, players, tournaments, smartFeed, calendar] = await Promise.all([
        api.live.list(),
        api.rankings.current(),
        api.news.featured().catch(() => api.news.list()),
        api.players.list({ page_size: 6 }),
        api.tournaments.list({ page_size: 4 }),
        api.users.smartFeed().catch(() => ({ data: { players: [], tournaments: [], matches: [], highlights: [] } })),
        api.users.calendar().catch(() => ({ data: { items: [] } })),
    ]);

    const liveList = extractList(live);
    const rankingList = extractList(rankings);
    const newsList = extractList(news);
    const playersList = extractList(players);
    const tournamentsList = extractList(tournaments);

    setText("home-live-count", liveList.length);
    setText("home-ranking-count", rankingList.length || 10);
    setText("home-news-count", newsList.length);
    setHtml("home-live-list", liveList.slice(0, 4).map(matchCard).join(""));
    setHtml("home-news-list", newsList.slice(0, 3).map(newsCard).join(""));
    setHtml("home-players-list", playersList.slice(0, 4).map(playerCard).join(""));
    setHtml("home-tournaments-list", tournamentsList.slice(0, 3).map(tournamentCard).join(""));
    setHtml("home-smart-players", (extractData(smartFeed).players || []).slice(0, 4).map(playerCard).join("") || '<div class="state-card">Добавляйте игроков в избранное и подписки.</div>');
    setHtml("home-smart-tournaments", (extractData(smartFeed).tournaments || []).slice(0, 4).map(tournamentCard).join("") || '<div class="state-card">Отмечайте турниры, чтобы они появились здесь.</div>');
    setHtml("home-calendar-list", ((extractData(calendar).items || []).slice(0, 4)).map(reminderCard).join("") || '<div class="state-card">Личный календарь пока пуст.</div>');
    setHtml("home-smart-highlights", (extractData(smartFeed).highlights || []).map((item) => `<span class="badge-soft">${escapeHtml(item)}</span>`).join(""));
}

async function initPlayers() {
    const render = async () => {
        renderSkeletonCards("players-grid", 6);
        try {
            const payload = await api.players.list({
                search: qs("#players-search")?.value.trim(),
                country_code: qs("#players-country")?.value,
                hand: qs("#players-hand")?.value,
                sort: qs("#players-sort")?.value,
            });
            renderState({
                targetId: "players-grid",
                items: extractList(payload),
                renderer: playerCard,
                emptyId: "players-empty",
                errorId: "players-error",
                emptyText: "Игроки не найдены. Попробуйте изменить фильтры.",
            });
        } catch (error) {
            renderState({ targetId: "players-grid", items: [], renderer: playerCard, error, errorId: "players-error", emptyId: "players-empty" });
        }
    };

    await render();
    ["#players-search", "#players-country", "#players-hand", "#players-sort"].forEach((selector) => {
        qs(selector)?.addEventListener("input", debounce(render, 260));
        qs(selector)?.addEventListener("change", render);
    });
    qs("#players-reset")?.addEventListener("click", () => {
        ["#players-search", "#players-country", "#players-hand", "#players-sort"].forEach((selector) => {
            const input = qs(selector);
            if (input) input.value = "";
        });
        render();
    });
}

async function initPlayerDetail() {
    const slug = slugFromPath();
    const playerId = await resolveEntityId(() => api.players.list({ page_size: 200 }), slug);
    if (!playerId) return;

    const [detailPayload, statsPayload, matchesPayload, rankingPayload, titlesPayload, newsPayload, upcomingPayload] = await Promise.all([
        api.players.detail(playerId),
        api.players.stats(playerId),
        api.players.matches(playerId),
        api.players.rankingHistory(playerId),
        api.players.titles(playerId),
        api.players.news(playerId),
        api.players.upcoming(playerId),
    ]);

    const detail = extractData(detailPayload);
    const stats = extractData(statsPayload);
    const upcoming = extractList(upcomingPayload);

    document.querySelectorAll("[data-favorite-button], [data-subscribe-button]").forEach((button) => {
        button.dataset.entityId = String(playerId);
    });

    setText("player-name", detail.full_name || "Игрок");
    setText("player-summary", detail.biography || "Профиль игрока, сезонные метрики и live-контекст.");
    setHtml(
        "player-badges",
        [
            detail.country_code && `<span class="badge-soft">${escapeHtml(detail.country_code)}</span>`,
            detail.current_rank && `<span class="badge-soft">Рейтинг №${escapeHtml(detail.current_rank)}</span>`,
            detail.current_points && `<span class="badge-soft">${escapeHtml(detail.current_points)} очков</span>`,
            detail.hand && `<span class="badge-soft">${escapeHtml(detail.hand)}</span>`,
        ]
            .filter(Boolean)
            .join(""),
    );
    setHtml(
        "player-photo",
        detail.photo_url
            ? `<img class="player-avatar--lg" src="${escapeHtml(detail.photo_url)}" alt="${escapeHtml(detail.full_name)}">`
            : `<div class="player-avatar--lg d-grid place-items-center"><div class="player-avatar__fallback">${escapeHtml(detail.full_name?.slice(0, 2) || "PL")}</div></div>`,
    );
    setHtml(
        "player-meta",
        `
            <div class="player-meta-card"><div class="text-muted small">Возраст</div><strong>${escapeHtml(detail.age || "-")}</strong></div>
            <div class="player-meta-card"><div class="text-muted small">Рост / Вес</div><strong>${escapeHtml(detail.height_cm || "-")} / ${escapeHtml(detail.weight_kg || "-")}</strong></div>
            <div class="player-meta-card"><div class="text-muted small">Рука</div><strong>${escapeHtml(detail.hand || "-")}</strong></div>
            <div class="player-meta-card"><div class="text-muted small">Бэкхенд</div><strong>${escapeHtml(detail.backhand || "-")}</strong></div>`,
    );
    setHtml(
        "player-form-chart",
        (detail.form || ["W", "W", "L", "W", "W"]).map((result, index) => `<div class="form-chart__bar" style="height:${result === "W" ? 90 - index * 8 : 36 + index * 5}%"></div>`).join(""),
    );
    setHtml(
        "player-stats-grid",
        [
            { label: "Матчи", value: stats.matches_played || stats.total_matches || "-" },
            { label: "Победы", value: stats.wins || "-" },
            { label: "Поражения", value: stats.losses || "-" },
            { label: "Эйсы", value: stats.aces || "-" },
            { label: "Спасенные брейк-пойнты", value: stats.break_points_saved_pct || "-" },
            { label: "Текущая серия", value: stats.current_streak || "-" },
        ]
            .map((item) => `<div class="metric-card"><div class="entity-card__eyebrow">${escapeHtml(item.label)}</div><div class="metric-value">${escapeHtml(item.value)}</div></div>`)
            .join(""),
    );
    setHtml("player-upcoming", upcoming.length ? upcoming.slice(0, 2).map(matchCard).join("") : '<div class="state-card">Нет ближайших матчей.</div>');
    setHtml("player-recent-matches", extractList(matchesPayload).slice(0, 5).map(matchCard).join("") || '<div class="state-card">Нет матчей.</div>');
    setHtml("player-ranking-history", extractList(rankingPayload).map(rankingRow).join(""));
    setHtml("player-titles", extractList(titlesPayload).map((item) => `<div class="entity-card"><div class="entity-card__eyebrow">${escapeHtml(item.category || "Титул")}</div><h3 class="entity-card__title">${escapeHtml(item.tournament_name || "-")}</h3><div class="entity-card__meta">${escapeHtml(item.surface || "")} • ${escapeHtml(item.season_year || "")}</div></div>`).join("") || '<div class="state-card">Титулов пока нет.</div>');
    setHtml("player-news", extractList(newsPayload).slice(0, 3).map(newsCard).join("") || '<div class="state-card">Нет связанных новостей.</div>');
}

async function initTournaments() {
    renderSkeletonCards("tournaments-grid", 6);
    try {
        const [payload, calendarPayload] = await Promise.all([api.tournaments.list(), api.tournaments.calendar().catch(() => ({ data: [] }))]);
        renderState({
            targetId: "tournaments-grid",
            items: extractList(payload),
            renderer: tournamentCard,
            emptyId: "tournaments-empty",
            errorId: "tournaments-error",
            emptyText: "Турниры по выбранным фильтрам не найдены.",
        });
        setHtml("tournaments-calendar", extractList(calendarPayload).slice(0, 3).map(tournamentCard).join("") || '<div class="state-card">Календарь пока пуст.</div>');
    } catch (error) {
        renderState({ targetId: "tournaments-grid", items: [], renderer: tournamentCard, error, errorId: "tournaments-error", emptyId: "tournaments-empty" });
    }
}

async function initTournamentDetail() {
    const slug = slugFromPath();
    const tournamentId = await resolveEntityId(() => api.tournaments.list({ page_size: 200 }), slug);
    if (!tournamentId) return;
    const [detailPayload, matchesPayload, drawPayload, playersPayload, championsPayload, newsPayload] = await Promise.all([
        api.tournaments.detail(tournamentId),
        api.tournaments.matches(tournamentId),
        api.tournaments.draw(tournamentId),
        api.tournaments.players(tournamentId).catch(() => ({ data: [] })),
        api.tournaments.champions(tournamentId),
        api.tournaments.news(tournamentId),
    ]);
    const detail = extractData(detailPayload);
    setText("tournament-name", detail.name || "Турнир");
    setText("tournament-summary", detail.description || "Календарь, draw, игроки и чемпионы турнира.");
    setHtml(
        "tournament-badges",
        [
            detail.category && `<span class="badge-soft">${escapeHtml(detail.category)}</span>`,
            detail.surface && `<span class="badge-soft">${escapeHtml(detail.surface)}</span>`,
            detail.city && `<span class="badge-soft">${escapeHtml(detail.city)}</span>`,
            detail.country_code && `<span class="badge-soft">${escapeHtml(detail.country_code)}</span>`,
        ]
            .filter(Boolean)
            .join(""),
    );
    setHtml("tournament-draw", extractList(drawPayload).slice(0, 8).map(matchCard).join("") || '<div class="state-card">Сетка будет опубликована позже.</div>');
    setHtml("tournament-matches", extractList(matchesPayload).slice(0, 6).map(matchCard).join(""));
    setHtml("tournament-players", extractList(playersPayload).slice(0, 6).map(playerCard).join("") || '<div class="state-card">Список игроков уточняется.</div>');
    setHtml("tournament-champions", extractList(championsPayload).map((item) => `<div class="entity-card"><div class="entity-card__eyebrow">${escapeHtml(item.season_year || "")}</div><h3 class="entity-card__title">${escapeHtml(item.player_name || "-")}</h3></div>`).join("") || '<div class="state-card">История чемпионов пока недоступна.</div>');
    setHtml("tournament-news", extractList(newsPayload).slice(0, 3).map(newsCard).join("") || '<div class="state-card">Нет новостей по турниру.</div>');
}

async function initMatches() {
    const render = async () => {
        renderSkeletonCards("matches-list", 6);
        try {
            const [payload, upcomingPayload, resultsPayload] = await Promise.all([
                api.matches.list({ status: qs("#matches-status")?.value }),
                api.matches.upcoming().catch(() => ({ data: [] })),
                api.matches.results().catch(() => ({ data: [] })),
            ]);
            renderState({
                targetId: "matches-list",
                items: extractList(payload),
                renderer: matchCard,
                emptyId: "matches-empty",
                errorId: "matches-error",
                emptyText: "Матчи по выбранным фильтрам не найдены.",
            });
            setHtml("matches-upcoming-list", extractList(upcomingPayload).slice(0, 6).map(matchCard).join("") || '<div class="state-card">Нет ближайших матчей.</div>');
            setHtml("matches-results-list", extractList(resultsPayload).slice(0, 6).map(matchCard).join("") || '<div class="state-card">Нет завершенных матчей.</div>');
        } catch (error) {
            renderState({ targetId: "matches-list", items: [], renderer: matchCard, error, errorId: "matches-error", emptyId: "matches-empty" });
        }
    };
    await render();
    qs("#matches-status")?.addEventListener("change", render);
}

async function initMatchDetail() {
    const slug = slugFromPath();
    const matchId = await resolveEntityId(() => api.matches.list({ page_size: 200 }), slug);
    if (!matchId) return;

    const render = async () => {
        const [detailPayload, statsPayload, timelinePayload, previewPayload, h2hPayload, pointPayload, scorePayload, predictionPayload, momentumPayload] = await Promise.all([
            api.matches.detail(matchId),
            api.matches.stats(matchId),
            api.matches.timeline(matchId),
            api.matches.preview(matchId),
            api.matches.h2h(matchId),
            api.matches.pointByPoint(matchId).catch(() => ({ data: [] })),
            api.matches.score(matchId).catch(() => ({ data: {} })),
            api.matches.prediction(matchId).catch(() => ({ data: {} })),
            api.matches.momentum(matchId).catch(() => ({ data: {} })),
        ]);
        const detail = extractData(detailPayload);
        const stats = extractData(statsPayload);
        const preview = extractData(previewPayload);
        const h2h = extractData(h2hPayload);
        const prediction = extractData(predictionPayload);
        const momentum = extractData(momentumPayload);

        setHtml("match-scoreboard", scoreboard(detail, detail.score || stats.score || {}));
        setHtml(
            "match-stats",
            [
                statPair("Эйсы", stats.player1_aces, stats.player2_aces),
                statPair("Первый мяч, %", stats.player1_first_serve_pct, stats.player2_first_serve_pct),
                statPair("Выигранные брейк-пойнты", stats.player1_break_points_won, stats.player2_break_points_won),
                statPair("Активно выигранные мячи", stats.player1_winners, stats.player2_winners),
            ].join(""),
        );
        setHtml("match-timeline", extractList(timelinePayload).map(timelineItem).join("") || '<div class="state-card">События еще не поступили.</div>');
        setHtml("match-preview", `<div class="text-muted">${escapeHtml((preview.notes || []).join(" ") || preview.summary || "Редакционный превью-блок будет доступен ближе к старту матча.")}</div>`);
        setHtml("match-prediction", predictionCard(prediction, detail));
        setHtml("match-momentum", momentumCard(momentum, detail));
        setHtml("match-score-service", `<pre class="mb-0 small">${escapeHtml(JSON.stringify(extractData(scorePayload), null, 2))}</pre>`);
        setHtml("match-h2h", `<div class="metric-value">${escapeHtml(h2h.player1_wins || 0)}:${escapeHtml(h2h.player2_wins || 0)}</div><div class="text-muted">Личных встреч: ${escapeHtml(h2h.total_matches || 0)}</div>`);
        setHtml(
            "match-h2h-history",
            [
                ...(Array.isArray(h2h.surface_split) ? h2h.surface_split.map((item) => `<div class="notification-item"><strong>${escapeHtml(item.surface)}</strong><div class="text-muted small mt-1">${escapeHtml(item.player1_wins)} : ${escapeHtml(item.player2_wins)}</div></div>`) : []),
                ...(Array.isArray(h2h.matches) ? h2h.matches.slice(0, 5).map((item) => `<div class="notification-item"><strong>${escapeHtml(item.tournament_name)}</strong><div class="text-muted small mt-1">${escapeHtml(item.surface || "-")} • ${escapeHtml(item.score_summary || "-")}</div></div>`) : []),
            ].join("") || '<div class="state-card">История очных встреч пока недоступна.</div>',
        );
        setHtml("match-points", extractList(pointPayload).slice(0, 10).map(timelineItem).join("") || '<div class="state-card">Пошаговая лента розыгрышей подключится во время матча.</div>');
        setHtml("match-news", (detail.related_news || []).map(newsCard).join("") || '<div class="state-card">Связанных новостей пока нет.</div>');
        setHtml("match-form", (detail.recent_matches || []).map(matchCard).join("") || '<div class="state-card">Последние матчи игроков еще не загружены.</div>');
    };

    await render();
    qs("#match-reminder-add")?.addEventListener("click", async () => {
        await api.users.addReminder({ match_id: matchId, remind_before_minutes: 30, channel: "web" });
    });
    qs("#match-subscribe-push")?.addEventListener("click", async () => {
        const permission = typeof Notification === "undefined" ? "unsupported" : await Notification.requestPermission();
        if (permission !== "granted") return;
        const endpoint = `browser://${window.location.host}/match/${matchId}`;
        await api.users.addPushSubscription({
            endpoint,
            device_label: `match-${matchId}`,
            keys_json: { matchId },
            permission,
        });
    });
    const refresh = debounce(render, 280);
    createLiveSocket([`live:match:${matchId}`], refresh);
}

async function initLiveCenter() {
    const render = async () => {
        try {
            const [matchesPayload, feedPayload] = await Promise.all([api.live.list(), api.live.feed()]);
            const matches = extractList(matchesPayload);
            renderState({
                targetId: "live-matches-list",
                items: matches,
                renderer: matchCard,
                emptyId: "live-matches-empty",
                errorId: "live-matches-error",
                emptyText: "Сейчас нет активных live-матчей.",
            });
            renderState({
                targetId: "live-feed-list",
                items: extractList(feedPayload),
                renderer: timelineItem,
                emptyId: "live-feed-empty",
                errorId: "live-feed-error",
                emptyText: "События live-ленты пока не поступали.",
            });
            const firstMatch = matches[0];
            if (firstMatch?.id) {
                const detailPayload = await api.live.detail(firstMatch.id).catch(() => ({ data: firstMatch }));
                setHtml("live-match-detail", matchCard({ ...extractData(detailPayload), slug: firstMatch.slug || "#" }));
            } else {
                setHtml("live-match-detail", '<div class="state-card">Выберите лайв-матч, чтобы увидеть детальную карточку.</div>');
            }
            setText("live-sync-status", `Обновлено ${formatDate(new Date())}`);
        } catch (error) {
            renderState({ targetId: "live-matches-list", items: [], renderer: matchCard, error, errorId: "live-matches-error", emptyId: "live-matches-empty" });
            renderState({ targetId: "live-feed-list", items: [], renderer: timelineItem, error, errorId: "live-feed-error", emptyId: "live-feed-empty" });
        }
    };
    await render();
    createLiveSocket(["live:all"], debounce(render, 260));
}

async function initRankings() {
    try {
        const [payload, fullPayload, racePayload, playersPayload] = await Promise.all([
            api.rankings.current(),
            api.rankings.list().catch(() => ({ data: [] })),
            api.rankings.race().catch(() => ({ data: [] })),
            api.players.list({ page_size: 100 }).catch(() => ({ data: [] })),
        ]);
        const list = extractList(payload);
        const fullList = extractList(fullPayload);
        const atp = list.filter((item) => String(item.tour || item.ranking_type || "ATP").toUpperCase().includes("ATP"));
        const wta = (fullList.length ? fullList : list).filter((item) => String(item.tour || item.ranking_type || "").toUpperCase().includes("WTA"));
        setHtml("rankings-atp-body", atp.map(rankingRow).join(""));
        setHtml("rankings-wta-body", (wta.length ? wta : atp).map(rankingRow).join(""));
        setText("rankings-date", extractData(payload).ranking_date || "Текущий срез");
        setHtml("rankings-race-list", extractList(racePayload).slice(0, 5).map((item) => `<div class="entity-card"><div class="entity-card__eyebrow">${escapeHtml(item.ranking_type || "Гонка")}</div><h3 class="entity-card__title">${escapeHtml(item.player_name || item.full_name || "-")}</h3><div class="entity-card__meta">${escapeHtml(item.points || "-")} очков</div></div>`).join("") || '<div class="state-card">Данные гонки сезона недоступны.</div>');
        const players = extractList(playersPayload);
        setHtml("rankings-player-select", `<option value="">Выберите игрока</option>${players.slice(0, 40).map((player) => `<option value="${escapeHtml(player.id)}">${escapeHtml(player.full_name)}</option>`).join("")}`);
        qs("#rankings-player-select")?.addEventListener("change", async () => {
            const playerId = qs("#rankings-player-select")?.value;
            if (!playerId) return;
            const [playerPayload, historyPayload] = await Promise.all([
                api.rankings.player(playerId).catch(() => ({ data: {} })),
                api.rankings.history("current", { player_id: playerId }).catch(() => ({ data: [] })),
            ]);
            const player = extractData(playerPayload);
            setHtml("rankings-player-card", `<div class="entity-card"><div class="entity-card__eyebrow">Рейтинг игрока</div><h3 class="entity-card__title">${escapeHtml(player.player_name || player.full_name || "Игрок")}</h3><div class="entity-card__meta">Позиция ${escapeHtml(player.rank_position || player.rank || "-")} • ${escapeHtml(player.points || "-")} очков</div></div>`);
            setHtml("rankings-history-body", extractList(historyPayload).map(rankingRow).join(""));
        });
    } catch (error) {
        show("rankings-error", true, error.message || "Не удалось загрузить рейтинги.");
    }
}

async function initH2H() {
    const playersPayload = await api.players.list({ page_size: 120 });
    const players = extractList(playersPayload);
    const options = players.map((player) => `<option value="${escapeHtml(player.id)}">${escapeHtml(player.full_name)}</option>`).join("");
    setHtml("h2h-player1", `<option value="">Игрок 1</option>${options}`);
    setHtml("h2h-player2", `<option value="">Игрок 2</option>${options}`);

    const render = async () => {
        const player1 = qs("#h2h-player1")?.value;
        const player2 = qs("#h2h-player2")?.value;
        if (!player1 || !player2) return;
        const [comparePayload, h2hPayload] = await Promise.all([api.players.compare({ player1_id: player1, player2_id: player2 }), api.players.h2h({ player1_id: player1, player2_id: player2 })]);
        const compare = extractData(comparePayload);
        const h2h = extractData(h2hPayload);
        setHtml(
            "h2h-summary",
            [
                `<div class="metric-card"><div class="entity-card__eyebrow">H2H</div><div class="metric-value">${escapeHtml(h2h.player1_wins || 0)}:${escapeHtml(h2h.player2_wins || 0)}</div></div>`,
                `<div class="metric-card"><div class="entity-card__eyebrow">Ranking</div><div class="metric-value">${escapeHtml(compare.player1_rank || "-")} / ${escapeHtml(compare.player2_rank || "-")}</div></div>`,
                `<div class="metric-card"><div class="entity-card__eyebrow">Win rate</div><div class="metric-value">${escapeHtml(compare.player1_win_pct || "-")}% / ${escapeHtml(compare.player2_win_pct || "-")}%</div></div>`,
            ].join(""),
        );
        const surfaces = Array.isArray(h2h.surface_split) ? h2h.surface_split : Array.isArray(h2h.surfaces) ? h2h.surfaces : [];
        const history = Array.isArray(h2h.matches) ? h2h.matches : [];
        setHtml("h2h-surface-split", surfaces.map((item) => `<tr><td>${escapeHtml(item.surface)}</td><td>${escapeHtml(item.player1_wins || 0)}</td><td>${escapeHtml(item.player2_wins || 0)}</td></tr>`).join(""));
        setHtml("h2h-history", history.map(matchCard).join("") || '<div class="state-card">История очных матчей не найдена.</div>');
    };
    qs("#h2h-compare")?.addEventListener("click", render);
}

async function initNews() {
    try {
        const [payload, categoriesPayload, tagsPayload] = await Promise.all([
            api.news.list(),
            api.news.categories().catch(() => ({ data: [] })),
            api.news.tags().catch(() => ({ data: [] })),
        ]);
        renderState({
            targetId: "news-grid",
            items: extractList(payload),
            renderer: newsCard,
            emptyId: "news-empty",
            errorId: "news-error",
            emptyText: "Пока нет опубликованных новостей.",
        });
        const categories = extractList(categoriesPayload);
        const tags = extractList(tagsPayload);
        setHtml("news-category-filter", `<option value="">Все категории</option>${categories.map((item) => `<option value="${escapeHtml(item.slug || item.id)}">${escapeHtml(item.name)}</option>`).join("")}`);
        setHtml("news-tag-filter", `<option value="">Все теги</option>${tags.map((item) => `<option value="${escapeHtml(item.slug || item.id)}">${escapeHtml(item.name)}</option>`).join("")}`);
    } catch (error) {
        renderState({ targetId: "news-grid", items: [], renderer: newsCard, error, errorId: "news-error", emptyId: "news-empty" });
    }
}

async function initNewsDetail() {
    const slug = slugFromPath();
    const payload = await api.news.detail(slug);
    const article = extractData(payload);
    setText("news-title", article.title || "Новость");
    setText("news-lead", article.lead || article.subtitle || "Редакционный материал.");
    setHtml("news-meta", `<span class="badge-soft">${escapeHtml(article.category?.name || article.status || "Новость")}</span><span class="badge-soft">${escapeHtml(formatDate(article.published_at))}</span>`);
    setHtml("news-content", article.content_html || `<p>${escapeHtml(article.content || article.body || "")}</p>`);
    const related = await api.news.related({ slug }).catch(() => ({ data: [] }));
    setHtml("news-related", extractList(related).map(newsCard).join("") || '<div class="state-card">Похожих материалов пока нет.</div>');
}

async function initSearch() {
    const render = async () => {
        const q = qs("#search-query")?.value.trim();
        if (!q) return;
        try {
            const payload = await api.search.query({ q });
            const data = extractData(payload);
            setHtml("search-all-results", extractList(payload).map((item) => `<a class="search-result" href="${escapeHtml(item.url || "#")}"><strong>${escapeHtml(item.title || item.label || item.slug)}</strong><span class="text-muted">${escapeHtml(item.type || "")}</span></a>`).join(""));
            setHtml("search-player-results", (data.players || []).map(playerCard).join("") || '<div class="state-card">Игроки не найдены.</div>');
            setHtml("search-news-results", (data.news || []).map(newsCard).join("") || '<div class="state-card">Новости не найдены.</div>');
            show("search-empty", !extractList(payload).length);
            show("search-error", false);
        } catch (error) {
            show("search-error", true, error.message || "Ошибка поиска");
        }
    };
    qs("#search-query")?.addEventListener("input", debounce(render, 260));
}

async function initAccount() {
    try {
        const [userPayload, favoritesPayload, subsPayload, calendarPayload, pushPayload] = await Promise.all([
            api.users.me(),
            api.users.favorites(),
            api.users.subscriptions(),
            api.users.calendar().catch(() => ({ data: { items: [] } })),
            api.users.pushSubscriptions().catch(() => ({ data: [] })),
        ]);
        const user = extractData(userPayload);
        setText("account-name", user.full_name || user.username || "Личный кабинет");
        const favorites = extractList(favoritesPayload);
        const subs = extractList(subsPayload);
        const calendar = extractData(calendarPayload).items || [];
        const pushDevices = extractList(pushPayload);
        show("account-favorites-empty", favorites.length === 0);
        show("account-subscriptions-empty", subs.length === 0);
        show("account-calendar-empty", calendar.length === 0);
        show("account-push-empty", pushDevices.length === 0);
        setHtml("account-favorites", favorites.map((item) => `<div class="notification-item"><strong>${escapeHtml(item.title || item.entity_type)}</strong><button class="btn btn-sm btn-outline-danger mt-2" data-favorite-remove="${escapeHtml(item.id || item.favorite_id || "")}">Удалить</button></div>`).join("") || "");
        setHtml("account-subscriptions", subs.map((item) => `<div class="notification-item"><strong>${escapeHtml(item.entity_type)}</strong><div class="text-muted small">${escapeHtml(item.channel || "web")}</div><div class="d-flex gap-2 mt-2"><button class="btn btn-sm btn-ghost-dark" data-subscription-update="${escapeHtml(item.id || "")}">Изменить</button><button class="btn btn-sm btn-outline-danger" data-subscription-remove="${escapeHtml(item.id || "")}">Удалить</button></div></div>`).join("") || "");
        setHtml("account-calendar", calendar.map(reminderCard).join("") || "");
        setHtml("account-push-list", pushDevices.map(pushDeviceCard).join("") || "");
        document.querySelectorAll("[data-favorite-remove]").forEach((button) => button.addEventListener("click", async () => {
            await api.users.removeFavorite(button.dataset.favoriteRemove);
            initAccount();
        }));
        document.querySelectorAll("[data-subscription-update]").forEach((button) => button.addEventListener("click", async () => {
            await api.users.updateSubscription(button.dataset.subscriptionUpdate, { channels: ["email"], notification_types: ["match_start"] });
            initAccount();
        }));
        document.querySelectorAll("[data-subscription-remove]").forEach((button) => button.addEventListener("click", async () => {
            await api.users.removeSubscription(button.dataset.subscriptionRemove);
            initAccount();
        }));
        document.querySelectorAll("[data-reminder-update]").forEach((button) => button.addEventListener("click", async () => {
            await api.users.updateReminder(button.dataset.reminderUpdate, { remind_before_minutes: 60 });
            initAccount();
        }));
        document.querySelectorAll("[data-reminder-remove]").forEach((button) => button.addEventListener("click", async () => {
            await api.users.removeReminder(button.dataset.reminderRemove);
            initAccount();
        }));
        document.querySelectorAll("[data-push-remove]").forEach((button) => button.addEventListener("click", async () => {
            await api.users.removePushSubscription(button.dataset.pushRemove);
            initAccount();
        }));
        qs("#account-user-notifications-load")?.addEventListener("click", async () => {
            const notificationsPayload = await api.users.notifications();
            const items = extractList(notificationsPayload);
            setHtml("account-user-notifications", items.map((item) => `<div class="notification-item"><strong>${escapeHtml(item.title || item.type || "Уведомление")}</strong><div class="text-muted small mt-1">${escapeHtml(item.body || "")}</div><button class="btn btn-sm btn-ghost-dark mt-2" data-user-notification-read="${escapeHtml(item.id)}">Прочитано</button></div>`).join("") || '<div class="state-card">Уведомлений нет.</div>');
            document.querySelectorAll("[data-user-notification-read]").forEach((button) => button.addEventListener("click", async () => {
                await api.users.readNotification(button.dataset.userNotificationRead);
                qs("#account-user-notifications-load")?.click();
            }));
        });
        qs("#account-user-notifications-read-all")?.addEventListener("click", async () => {
            await api.users.readAllNotifications();
            qs("#account-user-notifications-load")?.click();
        });
        qs("[data-auth-refresh]")?.addEventListener("click", async () => {
            await api.auth.refresh({});
            show("account-auth-feedback", true, "Сессия успешно обновлена.");
        });
        qs("#account-push-enable")?.addEventListener("click", async () => {
            const permission = typeof Notification === "undefined" ? "unsupported" : await Notification.requestPermission();
            if (permission === "denied" || permission === "unsupported") {
                show("account-error", true, "Браузерные уведомления недоступны или отклонены.");
                return;
            }
            const endpoint = `browser://${window.location.host}/${navigator.userAgent.slice(0, 48)}`;
            await api.users.addPushSubscription({
                endpoint,
                device_label: navigator.platform || "browser",
                keys_json: { userAgent: navigator.userAgent },
                permission,
            });
            initAccount();
        });
        qs("#account-push-test")?.addEventListener("click", async () => {
            await api.users.testPushSubscription({});
            if (typeof Notification !== "undefined" && Notification.permission === "granted") {
                new Notification("Тестовое уведомление", { body: "Браузерный канал подключен." });
            }
        });
    } catch (error) {
        show("account-error", true, error.message || "Не удалось загрузить аккаунт.");
    }
}

async function initNotificationsPage() {
    try {
        const payload = await api.notifications.list();
        const items = extractList(payload);
        setHtml("notifications-list", items.map((item) => `${notificationCard(item)}<button class="btn btn-sm btn-ghost-dark mt-2" data-notification-read="${escapeHtml(item.id)}">Отметить прочитанным</button>`).join(""));
        show("notifications-empty", items.length === 0);
        document.querySelectorAll("[data-notification-read]").forEach((button) => button.addEventListener("click", async () => {
            await api.notifications.read(button.dataset.notificationRead);
            initNotificationsPage();
        }));
        qs("#notifications-read-all-button")?.addEventListener("click", async () => {
            await api.notifications.readAll();
            initNotificationsPage();
        });
    } catch (error) {
        show("notifications-error", true, error.message || "Не удалось загрузить уведомления.");
    }
}

export async function initPublicPages() {
    const current = pageName();
    if (!current || current.startsWith("admin-")) return;
    const routes = {
        home: initHome,
        "players-list": initPlayers,
        "player-detail": initPlayerDetail,
        "tournaments-list": initTournaments,
        "tournament-detail": initTournamentDetail,
        "matches-list": initMatches,
        "match-detail": initMatchDetail,
        "live-center": initLiveCenter,
        rankings: initRankings,
        h2h: initH2H,
        "news-list": initNews,
        "news-detail": initNewsDetail,
        search: initSearch,
        account: initAccount,
        notifications: initNotificationsPage,
    };
    const init = routes[current];
    if (init) await init();
}
