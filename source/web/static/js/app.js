const API_BASE = "/api/v1";

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}

function extractList(payload) {
    if (!payload) return [];
    return Array.isArray(payload.data) ? payload.data : [];
}

async function apiRequest(path, options = {}) {
    const response = await fetch(`${API_BASE}${path}`, {
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        ...options,
    });
    const text = await response.text();
    let payload = null;
    try { payload = text ? JSON.parse(text) : null; } catch (_error) { payload = null; }
    if (!response.ok) {
        throw new Error(payload?.errors?.[0]?.message || `HTTP ${response.status}`);
    }
    return payload;
}

function apiGet(path) { return apiRequest(path); }

function setHtml(id, html) {
    const node = document.getElementById(id);
    if (node) node.innerHTML = html;
}

function showNode(id, visible, message = null) {
    const node = document.getElementById(id);
    if (!node) return;
    node.classList.toggle("d-none", !visible);
    if (message !== null) node.innerHTML = message;
}

function setLoadingCollection(targetId, columns = 1) {
    const skeleton = Array.from({ length: Math.max(columns, 1) }, () => '<div class="entity-card"><div class="skeleton card"></div></div>').join("");
    setHtml(targetId, skeleton);
}

function renderCollectionState({
    targetId,
    items,
    renderItem,
    emptyId = null,
    errorId = null,
    error = null,
    emptyMessage = null,
}) {
    if (errorId) showNode(errorId, Boolean(error), error ? escapeHtml(error.message || String(error)) : null);
    if (error) {
        setHtml(targetId, "");
        if (emptyId) showNode(emptyId, false);
        return;
    }
    const rendered = items.map(renderItem).join("");
    setHtml(targetId, rendered);
    if (emptyId) showNode(emptyId, items.length === 0, items.length === 0 ? escapeHtml(emptyMessage || "Нет данных") : null);
}

function wsBaseUrl(path) {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${window.location.host}${API_BASE}${path}`;
}

function createLiveSocket(channels, onEvent) {
    const socket = new WebSocket(wsBaseUrl(`/live/ws/live?channels=${encodeURIComponent(channels.join(","))}`));
    socket.addEventListener("message", (event) => {
        try {
            const payload = JSON.parse(event.data);
            if (payload.event === "connected") return;
            if (payload.event === "subscribed") return;
            onEvent(payload);
        } catch (_error) {
            return;
        }
    });
    return socket;
}

function debounce(fn, wait) {
    let timer = null;
    return (...args) => {
        window.clearTimeout(timer);
        timer = window.setTimeout(() => fn(...args), wait);
    };
}

function getEntitySlug() {
    return document.body.dataset.entitySlug || window.location.pathname.split("/").filter(Boolean).at(-1) || "";
}

function getEntityId() {
    return document.body.dataset.entityId || "";
}

function formatStatus(status) {
    return String(status || "").replaceAll("_", " ");
}

function formToJson(form) {
    const data = {};
    new FormData(form).forEach((value, key) => {
        if (value === "") return;
        if (key === "tag_ids") {
            data[key] = String(value).split(",").map((item) => item.trim()).filter(Boolean).map((item) => Number(item));
            return;
        }
        data[key] = value;
    });
    return data;
}

function showFormState(form, ok, message) {
    const success = form.querySelector("[data-form-feedback]");
    const error = form.querySelector("[data-form-error]");
    if (success) {
        success.classList.toggle("d-none", !ok);
        if (ok && message) success.textContent = message;
    }
    if (error) {
        error.classList.toggle("d-none", ok);
        if (!ok && message) error.textContent = message;
    }
}

function playerCard(player) {
    return `<a class="entity-card" href="/players/${escapeHtml(player.slug)}"><div class="d-flex justify-content-between"><span class="avatar-orb">${escapeHtml(player.full_name.split(" ").map((item) => item[0]).join("").slice(0, 2))}</span><span class="badge-soft">Место ${escapeHtml(player.current_rank ?? "-")}</span></div><h3 class="h5 mt-3">${escapeHtml(player.full_name)}</h3><div class="text-muted">${escapeHtml(player.country_code)}</div><div class="mt-2">Очки: ${escapeHtml(player.current_points ?? "-")}</div><div class="text-muted">Форма: ${escapeHtml((player.form || []).join(" "))}</div></a>`;
}

function tournamentCard(tournament) {
    return `<a class="entity-card" href="/tournaments/${escapeHtml(tournament.slug)}"><div class="badge-soft">${escapeHtml(formatStatus(tournament.category))}</div><h3 class="h5 mt-3">${escapeHtml(tournament.name)}</h3><div class="text-muted">${escapeHtml(tournament.city || "-")}, ${escapeHtml(tournament.surface)}</div><div class="mt-2">${escapeHtml(tournament.start_date || "")} - ${escapeHtml(tournament.end_date || "")}</div></a>`;
}

function matchCard(match) {
    const pillClass = match.status === "live" ? "live-pill" : "status-pill";
    return `<a class="entity-card" href="/matches/${escapeHtml(match.slug)}"><div class="d-flex justify-content-between flex-wrap gap-2"><div><strong>${escapeHtml(match.player1_name)} против ${escapeHtml(match.player2_name)}</strong><div class="text-muted">${escapeHtml(match.tournament_name)}${match.round_code ? `, ${escapeHtml(match.round_code)}` : ""}</div></div><span class="${pillClass}">${escapeHtml(formatStatus(match.status))}</span></div><div class="mt-2">${escapeHtml(match.score_summary || "Запланирован")}</div></a>`;
}

function newsCard(article) {
    return `<a class="entity-card" href="/news/${escapeHtml(article.slug)}"><span class="badge-soft">${escapeHtml(article.category?.name || article.status)}</span><h3 class="h5 mt-3">${escapeHtml(article.title)}</h3><p class="text-muted mb-0">${escapeHtml(article.lead || article.subtitle || "Редакционный материал")}</p></a>`;
}

function notificationCard(item) {
    return `<div class="timeline-item"><div class="timeline-time">${escapeHtml(item.type)}</div><strong>${escapeHtml(item.title)}</strong><div class="text-muted mt-1">${escapeHtml(item.body)}</div></div>`;
}

async function resolveEntityBySlug(listPath, slug) {
    const payload = await apiGet(listPath);
    return extractList(payload).find((item) => item.slug === slug) || null;
}

async function initHomePage() {
    const [livePayload, rankingPayload, newsPayload, playersPayload, tournamentsPayload] = await Promise.all([apiGet("/live"), apiGet("/rankings/current"), apiGet("/news"), apiGet("/players"), apiGet("/tournaments")]);
    const live = extractList(livePayload);
    const rankings = extractList(rankingPayload);
    const news = extractList(newsPayload);
    const players = extractList(playersPayload);
    const tournaments = extractList(tournamentsPayload);
    setHtml("home-live-count", String(live.length));
    setHtml("home-ranking-count", String(rankings.length));
    setHtml("home-news-count", String(news.length));
    setHtml("home-live-list", live.slice(0, 2).map(matchCard).join(""));
    setHtml("home-news-list", news.slice(0, 2).map(newsCard).join(""));
    setHtml("home-players-list", players.slice(0, 2).map((player) => `<a class="entity-card d-flex align-items-center gap-3" href="/players/${escapeHtml(player.slug)}"><span class="avatar-orb">${escapeHtml(player.full_name.split(" ").map((item) => item[0]).join("").slice(0, 2))}</span><div><strong>${escapeHtml(player.full_name)}</strong><div class="text-muted">№ ${escapeHtml(player.current_rank)}, ${escapeHtml(player.country_code)}</div></div></a>`).join(""));
    setHtml("home-tournaments-list", tournaments.slice(0, 2).map((item) => `<a class="entity-card" href="/tournaments/${escapeHtml(item.slug)}"><strong>${escapeHtml(item.name)}</strong><div class="text-muted">${escapeHtml(item.city || "-")}, ${escapeHtml(item.surface)}</div></a>`).join(""));
}

async function initPlayersListPage() {
    const search = document.getElementById("players-search");
    const country = document.getElementById("players-country");
    const hand = document.getElementById("players-hand");
    const empty = document.getElementById("players-empty");
    const render = async () => {
        const params = new URLSearchParams();
        if (search?.value) params.set("search", search.value);
        if (country?.value) params.set("country_code", country.value);
        if (hand?.value) params.set("hand", hand.value);
        const payload = await apiGet(`/players?${params.toString()}`);
        const players = extractList(payload);
        setHtml("players-grid", players.map(playerCard).join(""));
        if (empty) empty.classList.toggle("d-none", players.length !== 0);
    };
    await render();
    [search, country, hand].forEach((node) => node?.addEventListener("input", render));
    document.getElementById("players-reset")?.addEventListener("click", async () => {
        if (search) search.value = "";
        if (country) country.value = "";
        if (hand) hand.value = "";
        await render();
    });
}

async function initPlayerDetailPage() {
    const player = await resolveEntityBySlug("/players", getEntitySlug());
    if (!player) return;
    const [detail, statsPayload, matchesPayload, titlesPayload, newsPayload, rankingPayload] = await Promise.all([
        apiGet(`/players/${player.id}`),
        apiGet(`/players/${player.id}/stats`),
        apiGet(`/players/${player.id}/matches`),
        apiGet(`/players/${player.id}/titles`),
        apiGet(`/players/${player.id}/news`),
        apiGet(`/players/${player.id}/ranking-history`),
    ]);
    const data = detail.data;
    const stats = statsPayload.data;
    setHtml("player-name", escapeHtml(data.full_name));
    setHtml("player-summary", escapeHtml(`${data.country_name || data.country_code}, место ${data.current_rank}, ${data.current_points} очков`));
    setHtml("player-bio", escapeHtml(data.biography || ""));
    setHtml("player-badges", `<span class="badge-soft">${escapeHtml(data.country_code)}</span><span class="badge-soft">Место ${escapeHtml(data.current_rank)}</span><span class="badge-soft">${escapeHtml(data.hand || "-handed")}</span><button class="btn btn-success rounded-pill" data-loading-button>Подписаться</button>`);
    setHtml("player-upcoming-card", data.upcoming_match ? `<div class="text-muted">Следующий матч</div><strong>${escapeHtml(data.upcoming_match.tournament_name)}</strong><div class="text-muted">vs ${escapeHtml(data.upcoming_match.opponent_name)}</div><div class="mt-2">${escapeHtml(data.upcoming_match.scheduled_at)}</div>` : `<div class="text-muted">Ближайший матч пока не назначен.</div>`);
    setHtml("player-stats-grid", `<div class="entity-card"><strong>Матчи</strong><div class="metric-value">${escapeHtml(stats.matches_played)}</div></div><div class="entity-card"><strong>Процент побед</strong><div class="metric-value">${escapeHtml(stats.win_rate)}%</div></div><div class="entity-card"><strong>Хард</strong><div class="metric-value">${escapeHtml(stats.hard_record)}</div></div><div class="entity-card"><strong>Титулы</strong><div class="metric-value">${escapeHtml(stats.titles ?? 0)}</div></div><div class="entity-card"><strong>Финалы</strong><div class="metric-value">${escapeHtml(stats.finals ?? 0)}</div></div><div class="entity-card"><strong>Streak</strong><div class="metric-value">${escapeHtml(stats.current_streak ?? 0)}</div></div>`);
    setHtml("player-recent-matches", extractList(matchesPayload).map(matchCard).join(""));
    setHtml("player-ranking-history", extractList(rankingPayload).map((item) => `<tr><td>${escapeHtml(item.ranking_date)}</td><td>${escapeHtml(item.rank_position)}</td><td>${escapeHtml(item.points)}</td><td>${escapeHtml(item.movement)}</td></tr>`).join(""));
    setHtml("player-titles", extractList(titlesPayload).map((item) => `<div class="entity-card"><strong>${escapeHtml(item.tournament_name)}</strong><div class="text-muted">${escapeHtml(item.category)}, ${escapeHtml(item.surface)}</div></div>`).join(""));
    setHtml("player-news", extractList(newsPayload).map((item) => `<a class="entity-card d-block" href="/news/${escapeHtml(item.slug)}"><strong>${escapeHtml(item.title)}</strong><div class="text-muted">${escapeHtml(item.published_at || "")}</div></a>`).join(""));
    initLoadingButtons();
}

async function initTournamentsListPage() {
    setLoadingCollection("tournaments-grid", 3);
    try {
        const payload = await apiGet("/tournaments");
        renderCollectionState({
            targetId: "tournaments-grid",
            items: extractList(payload),
            renderItem: tournamentCard,
            emptyId: "tournaments-empty",
            errorId: "tournaments-error",
            emptyMessage: "Турниры по выбранным фильтрам не найдены.",
        });
    } catch (error) {
        renderCollectionState({ targetId: "tournaments-grid", items: [], renderItem: tournamentCard, emptyId: "tournaments-empty", errorId: "tournaments-error", error });
    }
}

async function initTournamentDetailPage() {
    const tournament = await resolveEntityBySlug("/tournaments", getEntitySlug());
    if (!tournament) return;
    const [detail, matches, draw, champions, news] = await Promise.all([apiGet(`/tournaments/${tournament.id}`), apiGet(`/tournaments/${tournament.id}/matches`), apiGet(`/tournaments/${tournament.id}/draw`), apiGet(`/tournaments/${tournament.id}/champions`), apiGet(`/tournaments/${tournament.id}/news`)]);
    const data = detail.data;
    setHtml("tournament-name", escapeHtml(data.name));
    setHtml("tournament-summary", escapeHtml(data.description || ""));
    setHtml("tournament-badges", `<span class="badge-soft">${escapeHtml(data.city || "-")}</span><span class="badge-soft">${escapeHtml(data.surface)}</span><span class="badge-soft">${escapeHtml(data.category)}</span>`);
    setHtml("tournament-draw", extractList(draw).map((item) => `<div class="entity-card"><strong>${escapeHtml(item.round_code)}</strong><div class="text-muted">${escapeHtml(item.player1_name)} против ${escapeHtml(item.player2_name)}</div><div>${escapeHtml(item.score_summary || "")}</div></div>`).join(""));
    setHtml("tournament-matches", extractList(matches).map(matchCard).join(""));
    setHtml("tournament-champions", extractList(champions).map((item) => `<div class="entity-card"><strong>${escapeHtml(item.season_year)}</strong><div class="text-muted">${escapeHtml(item.player_name)}</div></div>`).join(""));
    setHtml("tournament-news", extractList(news).map(newsCard).join(""));
}

async function initMatchesListPage() {
    const render = async () => {
        const status = document.getElementById("matches-status")?.value || "";
        const suffix = status ? `?status=${encodeURIComponent(status)}` : "";
        setLoadingCollection("matches-list", 2);
        try {
            const payload = await apiGet(`/matches${suffix}`);
            renderCollectionState({
                targetId: "matches-list",
                items: extractList(payload),
                renderItem: matchCard,
                emptyId: "matches-empty",
                errorId: "matches-error",
                emptyMessage: "Матчи по выбранным фильтрам не найдены.",
            });
        } catch (error) {
            renderCollectionState({ targetId: "matches-list", items: [], renderItem: matchCard, emptyId: "matches-empty", errorId: "matches-error", error });
        }
    };
    await render();
    document.getElementById("matches-filter")?.addEventListener("click", render);
}

async function initMatchDetailPage() {
    const match = await resolveEntityBySlug("/matches", getEntitySlug());
    if (!match) return;
    const render = async () => {
        const [detail, stats, timeline, preview, h2h] = await Promise.all([apiGet(`/matches/${match.id}`), apiGet(`/matches/${match.id}/stats`), apiGet(`/matches/${match.id}/timeline`), apiGet(`/matches/${match.id}/preview`), apiGet(`/matches/${match.id}/h2h`)]);
        const data = detail.data;
        setHtml("match-title", escapeHtml(`${data.player1_name} против ${data.player2_name}`));
        setHtml("match-subtitle", escapeHtml(`${data.tournament_name}${data.round_code ? `, ${data.round_code}` : ""}`));
        setHtml("match-status", escapeHtml(formatStatus(data.status)));
        setHtml("match-scoreboard", `<div class="score-line"><strong>${escapeHtml(data.player1_name)}</strong>${data.score.sets.map((set) => `<span>${escapeHtml(set.split("-")[0])}</span>`).join("")}</div><div class="score-line"><strong>${escapeHtml(data.player2_name)}</strong>${data.score.sets.map((set) => `<span>${escapeHtml(set.split("-")[1])}</span>`).join("")}</div>`);
        setHtml("match-stats-table", `<tr><td>Эйсы</td><td>${escapeHtml(stats.data.player1_aces)}</td><td>${escapeHtml(stats.data.player2_aces)}</td></tr><tr><td>% первой подачи</td><td>${escapeHtml(stats.data.player1_first_serve_pct)}</td><td>${escapeHtml(stats.data.player2_first_serve_pct)}</td></tr><tr><td>Длительность</td><td colspan="2">${escapeHtml(stats.data.duration_minutes)} мин</td></tr>`);
        setHtml("match-timeline", extractList(timeline).map((item) => `<div class="timeline-item"><div class="timeline-time">${escapeHtml(item.event_type)}</div><strong>${escapeHtml(JSON.stringify(item.payload_json))}</strong></div>`).join(""));
        setHtml("match-preview", `<div class="text-muted">${escapeHtml(preview.data.notes.join(" "))}</div>`);
        setHtml("match-h2h", `<div class="metric-value">${escapeHtml(h2h.data.player1_wins)} - ${escapeHtml(h2h.data.player2_wins)}</div><div class="text-muted">Всего матчей: ${escapeHtml(h2h.data.total_matches)}</div>`);
        setHtml("match-news", (data.related_news || []).map(newsCard).join(""));
    };
    await render();
    const refresh = debounce(render, 250);
    createLiveSocket([`live:match:${match.id}`], () => refresh());
}

async function initLiveCenterPage() {
    const render = async () => {
        try {
            const [matches, feed] = await Promise.all([apiGet("/live"), apiGet("/live/feed")]);
            renderCollectionState({ targetId: "live-matches-list", items: extractList(matches), renderItem: matchCard, emptyId: "live-matches-empty", errorId: "live-matches-error", emptyMessage: "Сейчас нет активных live-матчей." });
            renderCollectionState({ targetId: "live-feed-list", items: extractList(feed), renderItem: (item) => `<div class="timeline-item"><div class="timeline-time">${escapeHtml(item.event_type)}</div><strong>${escapeHtml(JSON.stringify(item.payload_json))}</strong></div>`, emptyId: "live-feed-empty", errorId: "live-feed-error", emptyMessage: "События live-ленты пока не поступали." });
        } catch (error) {
            renderCollectionState({ targetId: "live-matches-list", items: [], renderItem: matchCard, emptyId: "live-matches-empty", errorId: "live-matches-error", error });
            renderCollectionState({ targetId: "live-feed-list", items: [], renderItem: (item) => item, emptyId: "live-feed-empty", errorId: "live-feed-error", error });
        }
    };
    await render();
    const refresh = debounce(render, 250);
    createLiveSocket(["live:all"], () => refresh());
}

async function initRankingsPage() {
    try {
        const [atpPayload, wtaPayload] = await Promise.all([
            apiGet("/rankings/current?ranking_type=atp"),
            apiGet("/rankings/current?ranking_type=wta"),
        ]);
        const atp = extractList(atpPayload);
        const wta = extractList(wtaPayload);
        setHtml("rankings-date", escapeHtml(atp[0]?.ranking_date || wta[0]?.ranking_date || "-"));
        setHtml("rankings-atp-body", atp.map((item) => `<tr><td>${escapeHtml(item.position)}</td><td>${escapeHtml(item.movement)}</td><td>${escapeHtml(item.player_name)}</td><td>${escapeHtml(item.country_code)}</td><td>${escapeHtml(item.points)}</td></tr>`).join(""));
        setHtml("rankings-wta-body", wta.map((item) => `<tr><td>${escapeHtml(item.position)}</td><td>${escapeHtml(item.movement)}</td><td>${escapeHtml(item.player_name)}</td><td>${escapeHtml(item.country_code)}</td><td>${escapeHtml(item.points)}</td></tr>`).join(""));
        showNode("rankings-empty", atp.length === 0 && wta.length === 0, 'Данные рейтинга пока недоступны.');
        showNode("rankings-error", false);
    } catch (error) {
        setHtml("rankings-atp-body", "");
        setHtml("rankings-wta-body", "");
        showNode("rankings-empty", false);
        showNode("rankings-error", true, escapeHtml(error.message || String(error)));
    }
}

async function initNewsListPage() {
    const categorySelect = document.getElementById("news-category");
    const searchInput = document.getElementById("news-search");
    let allItems = [];
    const render = () => {
        const selectedCategory = categorySelect?.value || "";
        const query = searchInput?.value?.trim().toLowerCase() || "";
        const filtered = allItems.filter((item) => {
            const categoryOk = !selectedCategory || item.category?.slug === selectedCategory;
            const queryOk = !query || String(item.title || "").toLowerCase().includes(query) || String(item.lead || "").toLowerCase().includes(query);
            return categoryOk && queryOk;
        });
        renderCollectionState({
            targetId: "news-list-grid",
            items: filtered,
            renderItem: newsCard,
            emptyId: "news-list-empty",
            errorId: "news-list-error",
            emptyMessage: "По выбранным параметрам новости не найдены.",
        });
    };
    setLoadingCollection("news-list-grid", 2);
    try {
        const [newsPayload, categoriesPayload] = await Promise.all([apiGet("/news"), apiGet("/news/categories")]);
        allItems = extractList(newsPayload);
        if (categorySelect) categorySelect.innerHTML += extractList(categoriesPayload).map((item) => `<option value="${escapeHtml(item.slug)}">${escapeHtml(item.name)}</option>`).join("");
        render();
    } catch (error) {
        renderCollectionState({ targetId: "news-list-grid", items: [], renderItem: newsCard, emptyId: "news-list-empty", errorId: "news-list-error", error });
    }
    categorySelect?.addEventListener("change", render);
    searchInput?.addEventListener("input", debounce(render, 200));
}

async function initNewsDetailPage() {
    const data = (await apiGet(`/news/${getEntitySlug()}`)).data;
    setHtml("article-category", escapeHtml(data.category?.name || "Статья"));
    setHtml("article-title", escapeHtml(data.title));
    setHtml("article-meta", escapeHtml(`${data.published_at || ""} • ${data.status}`));
    setHtml("article-lead", escapeHtml(data.lead || ""));
    setHtml("article-content", data.content_html || "");
    setHtml("article-related", (data.related_news || []).map(newsCard).join(""));
}

async function initSearchPage() {
    const input = document.getElementById("search-query");
    const render = async () => {
        const query = input?.value?.trim() || "";
        if (!query) {
            renderCollectionState({ targetId: "search-all-results", items: [], renderItem: (item) => item, emptyId: "search-empty", errorId: "search-error", emptyMessage: "Введите запрос для поиска." });
            setHtml("search-player-results", "");
            setHtml("search-news-results", "");
            return;
        }
        setLoadingCollection("search-all-results", 2);
        try {
            const payload = await apiGet(`/search?q=${encodeURIComponent(query)}`);
            const data = payload.data;
            const allResults = [...data.players.map(playerCard), ...data.news.map(newsCard), ...data.matches.map(matchCard)];
            renderCollectionState({ targetId: "search-all-results", items: allResults, renderItem: (item) => item, emptyId: "search-empty", errorId: "search-error", emptyMessage: "Ничего не найдено по вашему запросу." });
            setHtml("search-player-results", data.players.map(playerCard).join(""));
            setHtml("search-news-results", data.news.map(newsCard).join(""));
        } catch (error) {
            renderCollectionState({ targetId: "search-all-results", items: [], renderItem: (item) => item, emptyId: "search-empty", errorId: "search-error", error });
            setHtml("search-player-results", "");
            setHtml("search-news-results", "");
        }
    };
    await render();
    input?.addEventListener("input", () => { window.clearTimeout(input._searchTimer); input._searchTimer = window.setTimeout(render, 250); });
}

async function initAccountPage() {
    try {
        const [me, favorites, subscriptions] = await Promise.all([apiGet("/users/me"), apiGet("/users/me/favorites"), apiGet("/users/me/subscriptions")]);
        setHtml("account-name", escapeHtml(`${me.data.first_name || ""} ${me.data.last_name || ""}`.trim() || me.data.username));
        const firstName = document.getElementById("account-first-name");
        const lastName = document.getElementById("account-last-name");
        const timezone = document.getElementById("account-timezone");
        if (firstName) firstName.value = me.data.first_name || "";
        if (lastName) lastName.value = me.data.last_name || "";
        if (timezone) timezone.value = me.data.timezone || "";
        renderCollectionState({ targetId: "account-favorites", items: extractList(favorites), renderItem: (item) => `<div class="entity-card"><strong>${escapeHtml(item.entity_name)}</strong><div class="text-muted">${escapeHtml(item.entity_type)}</div></div>`, emptyId: "account-favorites-empty", emptyMessage: "Избранное пока пустое." });
        renderCollectionState({ targetId: "account-subscriptions", items: extractList(subscriptions), renderItem: (item) => `<div class="entity-card"><strong>${escapeHtml(item.entity_type)} #${escapeHtml(item.entity_id)}</strong><div class="text-muted">${escapeHtml(item.notification_types.join(", "))}</div></div>`, emptyId: "account-subscriptions-empty", emptyMessage: "Подписок пока нет." });
        showNode("account-error", false);
    } catch (error) {
        showNode("account-error", true, escapeHtml(error.message || String(error)));
    }
}

async function initNotificationsPage() {
    try {
        const [count, list] = await Promise.all([apiGet("/notifications/unread-count"), apiGet("/notifications")]);
        setHtml("notifications-count", escapeHtml(`Непрочитано: ${count.data.unread_count}`));
        renderCollectionState({
            targetId: "notifications-list",
            items: extractList(list),
            renderItem: notificationCard,
            emptyId: "notifications-empty",
            errorId: "notifications-error",
            emptyMessage: "Уведомлений пока нет.",
        });
    } catch (error) {
        renderCollectionState({ targetId: "notifications-list", items: [], renderItem: notificationCard, emptyId: "notifications-empty", errorId: "notifications-error", error });
    }
}

async function initH2HPage() {
    const playersPayload = await apiGet("/players");
    const players = extractList(playersPayload);
    const player1Select = document.getElementById("h2h-player1");
    const player2Select = document.getElementById("h2h-player2");
    const options = players.map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.full_name)}</option>`).join("");
    if (player1Select) player1Select.innerHTML = options;
    if (player2Select) player2Select.innerHTML = options;
    if (player1Select && !player1Select.value && players[0]) player1Select.value = String(players[0].id);
    if (player2Select && !player2Select.value && players[1]) player2Select.value = String(players[1].id);
    const render = async () => {
        const player1Id = player1Select?.value;
        const player2Id = player2Select?.value;
        if (!player1Id || !player2Id || player1Id === player2Id) return;
        const [h2hPayload, comparePayload] = await Promise.all([
            apiGet(`/players/h2h?player1_id=${encodeURIComponent(player1Id)}&player2_id=${encodeURIComponent(player2Id)}`),
            apiGet(`/players/compare?player1_id=${encodeURIComponent(player1Id)}&player2_id=${encodeURIComponent(player2Id)}`),
        ]);
        const h2h = h2hPayload.data;
        const compare = comparePayload.data;
        setHtml("h2h-summary", `<div class="metric-card"><div class="eyebrow">Всего</div><div class="metric-value">${escapeHtml(h2h.total_matches)}</div></div><div class="metric-card"><div class="eyebrow">${escapeHtml(compare.player1.full_name)} побед</div><div class="metric-value">${escapeHtml(h2h.player1_wins)}</div></div><div class="metric-card"><div class="eyebrow">${escapeHtml(compare.player2.full_name)} побед</div><div class="metric-value">${escapeHtml(h2h.player2_wins)}</div></div>`);
        setHtml("h2h-surface-split", `<tr><td>Хард</td><td>${escapeHtml(h2h.hard_player1_wins)}</td><td>${escapeHtml(h2h.hard_player2_wins)}</td></tr><tr><td>Clay</td><td>${escapeHtml(h2h.clay_player1_wins)}</td><td>${escapeHtml(h2h.clay_player2_wins)}</td></tr><tr><td>Grass</td><td>${escapeHtml(h2h.grass_player1_wins)}</td><td>${escapeHtml(h2h.grass_player2_wins)}</td></tr>`);
        setHtml("h2h-history", `<div class="entity-card"><strong>Последний матч #${escapeHtml(h2h.last_match_id || "-")}</strong><div class="text-muted">${escapeHtml(compare.player1.full_name)} против ${escapeHtml(compare.player2.full_name)}</div><div class="mt-2">Текущий H2H: ${escapeHtml(h2h.player1_wins)}-${escapeHtml(h2h.player2_wins)}</div></div>`);
    };
    await render();
    player1Select?.addEventListener("change", render);
    player2Select?.addEventListener("change", render);
    document.getElementById("h2h-compare")?.addEventListener("click", render);
}

async function initAdminDashboard() {
    const [live, news, integrations, audit, jobs] = await Promise.all([apiGet("/live"), apiGet("/admin/news"), apiGet("/admin/integrations"), apiGet("/admin/audit-logs"), apiGet("/admin/jobs")]);
    setHtml("admin-live-count", String(extractList(live).length));
    setHtml("admin-news-count", String(extractList(news).length));
    setHtml("admin-integrations-count", String(extractList(integrations).length));
    setHtml("admin-jobs-count", String(extractList(jobs).length));
    setHtml("admin-audit-list", extractList(audit).map((item) => `<div class="timeline-item"><div class="timeline-time">${escapeHtml(item.created_at)}</div><strong>${escapeHtml(item.action)}</strong><div class="text-muted">${escapeHtml(item.entity_type)} #${escapeHtml(item.entity_id)}</div></div>`).join(""));
    setHtml("admin-integrations-list", extractList(integrations).map((item) => `<div class="entity-card"><strong>${escapeHtml(item.provider)}</strong><div class="text-muted">${escapeHtml(item.status)}</div></div>`).join(""));
}

async function initAdminTable(path, targetId, rowBuilder) { setHtml(targetId, extractList(await apiGet(path)).map(rowBuilder).join("")); }







async function initAdminTournamentsPage() {
    const form = document.getElementById("admin-tournaments-filters");
    const resetButton = document.getElementById("admin-tournaments-reset");
    const render = async () => {
        const params = new URLSearchParams();
        const search = document.getElementById("admin-tournaments-search")?.value?.trim() || "";
        const category = document.getElementById("admin-tournaments-category")?.value?.trim() || "";
        const surface = document.getElementById("admin-tournaments-surface")?.value || "";
        const status = document.getElementById("admin-tournaments-status")?.value || "";
        const seasonYear = document.getElementById("admin-tournaments-season")?.value?.trim() || "";
        if (search) params.set("search", search);
        if (category) params.set("category", category);
        if (surface) params.set("surface", surface);
        if (status) params.set("status", status);
        if (seasonYear) params.set("season_year", seasonYear);
        const suffix = params.toString() ? `?${params.toString()}` : "";
        const payload = await apiGet(`/admin/tournaments${suffix}`);
        setHtml("admin-tournaments-body", extractList(payload).map((item) => `<tr><td>${escapeHtml(item.name)}</td><td>${escapeHtml(item.category)}</td><td>${escapeHtml(item.surface)}</td><td>${escapeHtml(item.status)}</td><td class="d-flex gap-2"><button class="btn btn-sm btn-outline-dark" type="button" data-tournament-draw="${escapeHtml(item.id)}">Draw</button><button class="btn btn-sm btn-success" type="button" data-tournament-publish="${escapeHtml(item.id)}">Publish</button></td></tr>`).join(""));
        document.querySelectorAll("[data-tournament-draw]").forEach((button) => button.addEventListener("click", async () => { await apiRequest(`/admin/tournaments/${button.dataset.tournamentDraw}/draw/generate`, { method: "POST" }); }));
        document.querySelectorAll("[data-tournament-publish]").forEach((button) => button.addEventListener("click", async () => { await apiRequest(`/admin/tournaments/${button.dataset.tournamentPublish}/publish`, { method: "POST" }); }));
    };
    await render();
    form?.addEventListener("submit", async (event) => {
        event.preventDefault();
        await render();
    });
    document.getElementById("admin-tournaments-search")?.addEventListener("input", debounce(render, 250));
    resetButton?.addEventListener("click", async () => {
        form?.reset();
        await render();
    });
}

async function initAdminUsersPage() {
    const form = document.getElementById("admin-users-filters");
    const resetButton = document.getElementById("admin-users-reset");
    const render = async () => {
        const params = new URLSearchParams();
        const search = document.getElementById("admin-users-search")?.value?.trim() || "";
        const role = document.getElementById("admin-users-role")?.value || "";
        const status = document.getElementById("admin-users-status")?.value || "";
        if (search) params.set("search", search);
        if (role) params.set("role", role);
        if (status) params.set("status", status);
        const suffix = params.toString() ? `?${params.toString()}` : "";
        const payload = await apiGet(`/admin/users${suffix}`);
        setHtml("admin-users-body", extractList(payload).map((item) => `<tr><td>${escapeHtml(item.id)}</td><td>${escapeHtml(item.email)}</td><td>${escapeHtml(item.username)}</td><td>${escapeHtml(item.role)}</td><td>${escapeHtml(item.status)}</td><td>${item.status !== "deleted" ? `<button class="btn btn-sm btn-outline-danger" type="button" data-user-delete="${escapeHtml(item.id)}">Delete</button>` : "-"}</td></tr>`).join(""));
        document.querySelectorAll("[data-user-delete]").forEach((button) => {
            button.addEventListener("click", async () => {
                await apiRequest(`/admin/users/${button.dataset.userDelete}`, { method: "DELETE" });
                await render();
            });
        });
    };
    await render();
    form?.addEventListener("submit", async (event) => {
        event.preventDefault();
        await render();
    });
    resetButton?.addEventListener("click", async () => {
        form?.reset();
        await render();
    });
}

async function initAdminMatchesPage() {
    const form = document.getElementById("admin-matches-filters");
    const resetButton = document.getElementById("admin-matches-reset");
    let searchTimer = null;
    const render = async () => {
        const params = new URLSearchParams();
        const search = document.getElementById("admin-matches-search")?.value?.trim() || "";
        const status = document.getElementById("admin-matches-status")?.value || "";
        const tournamentId = document.getElementById("admin-matches-tournament")?.value?.trim() || "";
        const playerId = document.getElementById("admin-matches-player")?.value?.trim() || "";
        const roundCode = document.getElementById("admin-matches-round")?.value?.trim() || "";
        const dateFrom = document.getElementById("admin-matches-date-from")?.value || "";
        const dateTo = document.getElementById("admin-matches-date-to")?.value || "";
        if (search) params.set("search", search);
        if (status) params.set("status", status);
        if (tournamentId) params.set("tournament_id", tournamentId);
        if (playerId) params.set("player_id", playerId);
        if (roundCode) params.set("round_code", roundCode);
        if (dateFrom) params.set("date_from", dateFrom);
        if (dateTo) params.set("date_to", dateTo);
        const suffix = params.toString() ? `?${params.toString()}` : "";
        const payload = await apiGet(`/admin/matches${suffix}`);
        setHtml(
            "admin-matches-body",
            extractList(payload).map((item) => `<tr><td>${escapeHtml(item.player1_name)} против ${escapeHtml(item.player2_name)}</td><td>${escapeHtml(item.tournament_name)}</td><td>${escapeHtml(item.status)}</td><td>${escapeHtml(item.round_code || "-")}</td><td>${escapeHtml(item.scheduled_at || "-")}</td><td class="d-flex gap-2"><a class="btn btn-sm btn-outline-dark" href="/admin/matches/${escapeHtml(item.id)}">Open</a>${item.status !== "finished" ? `<button class="btn btn-sm btn-success" type="button" data-match-finalize="${escapeHtml(item.id)}">Finalize</button>` : `<button class="btn btn-sm btn-outline-secondary" type="button" data-match-reopen="${escapeHtml(item.id)}">Reopen</button>`}</td></tr>`).join(""),
        );
        document.querySelectorAll("[data-match-finalize]").forEach((button) => {
            button.addEventListener("click", async () => {
                await apiRequest(`/admin/matches/${button.dataset.matchFinalize}/finalize`, { method: "POST" });
                await render();
            });
        });
        document.querySelectorAll("[data-match-reopen]").forEach((button) => {
            button.addEventListener("click", async () => {
                await apiRequest(`/admin/matches/${button.dataset.matchReopen}/reopen`, { method: "POST" });
                await render();
            });
        });
    };
    await render();
    form?.addEventListener("submit", async (event) => {
        event.preventDefault();
        await render();
    });
    document.getElementById("admin-matches-search")?.addEventListener("input", () => {
        window.clearTimeout(searchTimer);
        searchTimer = window.setTimeout(() => { void render(); }, 250);
    });
    resetButton?.addEventListener("click", async () => {
        form?.reset();
        await render();
    });
}

async function initAdminPlayersPage() {
    const form = document.getElementById("admin-players-filters");
    const resetButton = document.getElementById("admin-players-reset");
    const importForm = document.getElementById("admin-player-import-form");
    const importJson = document.getElementById("admin-player-import-json");
    const importFeedback = document.getElementById("admin-player-import-feedback");
    const importError = document.getElementById("admin-player-import-error");
    const showImportState = (ok, message) => {
        if (importFeedback) {
            importFeedback.classList.toggle("d-none", !ok);
            importFeedback.textContent = ok ? message : importFeedback.textContent;
        }
        if (importError) {
            importError.classList.toggle("d-none", ok);
            importError.textContent = ok ? importError.textContent : message;
        }
    };
    const render = async () => {
        const params = new URLSearchParams();
        const search = document.getElementById("admin-players-search")?.value?.trim() || "";
        const countryCode = document.getElementById("admin-players-country")?.value?.trim() || "";
        const hand = document.getElementById("admin-players-hand")?.value || "";
        const status = document.getElementById("admin-players-status")?.value || "";
        if (search) params.set("search", search);
        if (countryCode) params.set("country_code", countryCode);
        if (hand) params.set("hand", hand);
        if (status) params.set("status", status);
        const suffix = params.toString() ? `?${params.toString()}` : "";
        const payload = await apiGet(`/admin/players${suffix}`);
        setHtml("admin-players-body", extractList(payload).map((item) => `<tr><td>${escapeHtml(item.full_name)}</td><td>${escapeHtml(item.country_code)}</td><td>${escapeHtml(item.current_rank)}</td><td>${escapeHtml(item.form?.length ? "active" : "active")}</td><td class="d-flex gap-2"><button class="btn btn-sm btn-outline-dark" type="button" data-player-photo="${escapeHtml(item.id)}">Photo</button><button class="btn btn-sm btn-success" type="button" data-player-recalc="${escapeHtml(item.id)}">Recalc</button></td></tr>`).join(""));
        document.querySelectorAll("[data-player-photo]").forEach((button) => {
            button.addEventListener("click", async () => {
                const value = window.prompt("Введите URL фото игрока");
                if (!value) return;
                await apiRequest(`/admin/players/${button.dataset.playerPhoto}/photo`, { method: "POST", body: JSON.stringify({ photo_url: value }) });
                await render();
            });
        });
        document.querySelectorAll("[data-player-recalc]").forEach((button) => {
            button.addEventListener("click", async () => {
                await apiRequest(`/admin/players/${button.dataset.playerRecalc}/recalculate-stats`, { method: "POST" });
            });
        });
    };
    await render();
    form?.addEventListener("submit", async (event) => {
        event.preventDefault();
        await render();
    });
    document.getElementById("admin-players-search")?.addEventListener("input", debounce(render, 250));
    resetButton?.addEventListener("click", async () => {
        form?.reset();
        await render();
    });
    importForm?.addEventListener("submit", async (event) => {
        event.preventDefault();
        try {
            const players = JSON.parse(importJson?.value || '[]');
            const payload = await apiRequest("/admin/players/import", { method: "POST", body: JSON.stringify({ players }) });
            showImportState(true, payload?.data?.message || "Импорт выполнен.");
            await render();
        } catch (error) {
            showImportState(false, error.message);
        }
    });
}

async function initAdminMaintenancePage() {
    const feedback = document.getElementById("admin-maintenance-feedback");
    const errorNode = document.getElementById("admin-maintenance-error");
    const showState = (ok, message) => {
        if (feedback) {
            feedback.classList.toggle("d-none", !ok);
            feedback.textContent = ok ? message : feedback.textContent;
        }
        if (errorNode) {
            errorNode.classList.toggle("d-none", ok);
            errorNode.textContent = ok ? errorNode.textContent : message;
        }
    };
    const render = async () => {
        const payload = await apiGet("/admin/maintenance");
        const items = extractList(payload);
        setHtml(
            "admin-maintenance-body",
            items.map((item) => `<tr><td>${escapeHtml(item.code)}</td><td>${escapeHtml(item.exists ? "yes" : "no")}</td><td>${escapeHtml(item.updated_at || "-")}</td><td>${escapeHtml(item.path)}</td></tr>`).join(""),
        );
        showNode("admin-maintenance-empty", items.every((item) => !item.exists), 'Maintenance-артефакты пока не созданы.');
    };
    document.querySelectorAll("[data-maintenance-run]").forEach((button) => {
        button.addEventListener("click", async () => {
            try {
                const payload = await apiRequest("/admin/maintenance/run", { method: "POST", body: JSON.stringify({ job_type: button.dataset.maintenanceRun }) });
                showState(true, `Запущена задача ${payload?.data?.job_type} #${payload?.data?.job_id}.`);
                await render();
            } catch (error) {
                showState(false, error.message);
            }
        });
    });
    await render();
}

async function initAdminJobsPage() {
    const feedback = document.getElementById("admin-jobs-feedback");
    const errorNode = document.getElementById("admin-jobs-error");
    const showState = (ok, message) => {
        if (feedback) {
            feedback.classList.toggle("d-none", !ok);
            feedback.textContent = ok ? message : feedback.textContent;
        }
        if (errorNode) {
            errorNode.classList.toggle("d-none", ok);
            errorNode.textContent = ok ? errorNode.textContent : message;
        }
    };
    const render = async () => {
        const payload = await apiGet("/admin/jobs");
        const items = extractList(payload);
        setHtml(
            "admin-jobs-body",
            items.map((item) => `<tr><td>${escapeHtml(item.id)}</td><td>${escapeHtml(item.job_type)}</td><td>${escapeHtml(item.status)}</td><td>${escapeHtml(item.run_at)}</td><td>${escapeHtml(item.attempts)}</td><td>${escapeHtml(item.error || "-")}</td><td>${item.status === "failed" ? `<button class="btn btn-sm btn-outline-dark" type="button" data-job-retry="${escapeHtml(item.id)}">Retry</button>` : "-"}</td></tr>`).join(""),
        );
        showNode("admin-jobs-empty", items.length === 0, 'Очередь задач сейчас пуста.');
        document.querySelectorAll("[data-job-retry]").forEach((button) => {
            button.addEventListener("click", async () => {
                try {
                    await apiRequest(`/admin/jobs/${button.dataset.jobRetry}/retry`, { method: "POST" });
                    showState(true, `Job ${button.dataset.jobRetry} повторно поставлен в очередь.`);
                    await render();
                } catch (error) {
                    showState(false, error.message);
                }
            });
        });
    };
    document.getElementById("admin-jobs-process")?.addEventListener("click", async () => {
        try {
            const payload = await apiRequest("/admin/jobs/process", { method: "POST" });
            showState(true, payload?.data?.message || "Pending jobs обработаны.");
            await render();
        } catch (error) {
            showState(false, error.message);
        }
    });
    document.getElementById("admin-jobs-prune")?.addEventListener("click", async () => {
        try {
            const payload = await apiRequest("/admin/jobs/prune", { method: "POST", body: JSON.stringify({}) });
            showState(true, `Удалено ${payload?.data?.removed ?? 0} задач.`);
            await render();
        } catch (error) {
            showState(false, error.message);
        }
    });
    await render();
}

async function initAdminAuditPage() {
    const form = document.getElementById("admin-audit-filters");
    const resetButton = document.getElementById("admin-audit-reset");
    const render = async () => {
        const params = new URLSearchParams();
        const userId = document.getElementById("audit-user-id")?.value?.trim() || "";
        const entityType = document.getElementById("audit-entity-type")?.value?.trim() || "";
        const action = document.getElementById("audit-action")?.value?.trim() || "";
        const dateFrom = document.getElementById("audit-date-from")?.value || "";
        const dateTo = document.getElementById("audit-date-to")?.value || "";
        if (userId) params.set("user_id", userId);
        if (entityType) params.set("entity_type", entityType);
        if (action) params.set("action", action);
        if (dateFrom) params.set("date_from", dateFrom);
        if (dateTo) params.set("date_to", dateTo);
        const suffix = params.toString() ? `?${params.toString()}` : "";
        const payload = await apiGet(`/admin/audit-logs${suffix}`);
        setHtml(
            "admin-audit-body",
            extractList(payload).map((item) => `<tr><td>${escapeHtml(item.action)}</td><td>${escapeHtml(item.entity_type)} #${escapeHtml(item.entity_id)}</td><td>${escapeHtml(item.user_id || "-")}</td><td>${escapeHtml(item.created_at)}</td></tr>`).join(""),
        );
    };
    await render();
    form?.addEventListener("submit", async (event) => {
        event.preventDefault();
        await render();
    });
    resetButton?.addEventListener("click", async () => {
        form?.reset();
        await render();
    });
}

async function initAdminNewsPage() {
    const form = document.getElementById("admin-news-filters");
    const resetButton = document.getElementById("admin-news-reset");
    const feedback = document.getElementById("admin-news-feedback");
    const errorNode = document.getElementById("admin-news-error");
    let searchTimer = null;
    const showState = (ok, message) => {
        if (feedback) {
            feedback.classList.toggle("d-none", !ok);
            feedback.textContent = ok ? message : feedback.textContent;
        }
        if (errorNode) {
            errorNode.classList.toggle("d-none", ok);
            errorNode.textContent = ok ? errorNode.textContent : message;
        }
    };
    const render = async () => {
        const params = new URLSearchParams();
        const search = document.getElementById("admin-news-search")?.value?.trim() || "";
        const status = document.getElementById("admin-news-status")?.value || "";
        if (search) params.set("search", search);
        if (status) params.set("status", status);
        const suffix = params.toString() ? `?${params.toString()}` : "";
        const payload = await apiGet(`/admin/news${suffix}`);
        setHtml(
            "admin-news-body",
            extractList(payload).map((item) => `<tr><td>${escapeHtml(item.title)}</td><td>${escapeHtml(item.status)}</td><td>${escapeHtml(item.published_at || "-")}</td><td>${(item.tags || []).map((tag) => escapeHtml(tag.name)).join(", ") || "-"}</td><td class="d-flex gap-2"><button class="btn btn-sm btn-outline-dark" type="button" data-news-cover="${escapeHtml(item.id)}">Cover</button><button class="btn btn-sm btn-success" type="button" data-news-tags="${escapeHtml(item.id)}">Tags</button>${item.status !== "published" ? `<button class="btn btn-sm btn-outline-primary" type="button" data-news-publish="${escapeHtml(item.id)}">Publish</button>` : ""}</td></tr>`).join(""),
        );
        document.querySelectorAll("[data-news-cover]").forEach((button) => button.addEventListener("click", async () => {
            const value = window.prompt("Введите URL cover image");
            if (!value) return;
            try {
                await apiRequest(`/admin/news/${button.dataset.newsCover}/cover`, { method: "POST", body: JSON.stringify({ cover_image_url: value }) });
                showState(true, "Cover обновлен.");
                await render();
            } catch (error) {
                showState(false, error.message);
            }
        }));
        document.querySelectorAll("[data-news-tags]").forEach((button) => button.addEventListener("click", async () => {
            const value = window.prompt("Введите ID тегов через запятую");
            if (value === null) return;
            const tagIds = value.split(",").map((item) => item.trim()).filter(Boolean).map((item) => Number(item));
            try {
                await apiRequest(`/admin/news/${button.dataset.newsTags}/tags`, { method: "POST", body: JSON.stringify({ tag_ids: tagIds }) });
                showState(true, "Теги обновлены.");
                await render();
            } catch (error) {
                showState(false, error.message);
            }
        }));
        document.querySelectorAll("[data-news-publish]").forEach((button) => button.addEventListener("click", async () => {
            try {
                await apiRequest(`/admin/news/${button.dataset.newsPublish}/publish`, { method: "POST" });
                showState(true, "Статья опубликована.");
                await render();
            } catch (error) {
                showState(false, error.message);
            }
        }));
    };
    await render();
    form?.addEventListener("submit", async (event) => {
        event.preventDefault();
        await render();
    });
    document.getElementById("admin-news-search")?.addEventListener("input", () => {
        window.clearTimeout(searchTimer);
        searchTimer = window.setTimeout(() => { void render(); }, 250);
    });
    resetButton?.addEventListener("click", async () => {
        form?.reset();
        await render();
    });
}

async function initAdminIntegrationsPage() {
    const filterForm = document.getElementById("admin-integrations-filters");
    const resetButton = document.getElementById("admin-integrations-reset");
    const updateForm = document.getElementById("admin-integrations-update-form");
    const syncButton = document.getElementById("admin-integrations-sync");
    const logsButton = document.getElementById("admin-integrations-load-logs");
    const providerInput = document.getElementById("admin-integrations-target");
    const endpointInput = document.getElementById("admin-integrations-endpoint");
    const feedback = document.getElementById("admin-integrations-feedback");
    const errorNode = document.getElementById("admin-integrations-error");
    const showState = (ok, message) => {
        if (feedback) {
            feedback.classList.toggle("d-none", !ok);
            feedback.textContent = ok ? message : feedback.textContent;
        }
        if (errorNode) {
            errorNode.classList.toggle("d-none", ok);
            errorNode.textContent = ok ? errorNode.textContent : message;
        }
    };
    const renderLogs = async (provider) => {
        const payload = await apiGet(`/admin/integrations/${encodeURIComponent(provider)}/logs`);
        setHtml("admin-integrations-logs", extractList(payload).map((item) => `<div class="timeline-item"><div class="timeline-time">${escapeHtml(item.timestamp)}</div><strong>${escapeHtml(item.level)}</strong><div class="text-muted">${escapeHtml(item.message)}</div></div>`).join("") || '<div class="text-muted">Логи отсутствуют</div>');
    };
    const render = async () => {
        const params = new URLSearchParams();
        const provider = document.getElementById("admin-integrations-provider")?.value?.trim() || "";
        const status = document.getElementById("admin-integrations-status")?.value || "";
        if (provider) params.set("provider", provider);
        if (status) params.set("status", status);
        const suffix = params.toString() ? `?${params.toString()}` : "";
        const payload = await apiGet(`/admin/integrations${suffix}`);
        const items = extractList(payload);
        setHtml("admin-integrations-body", items.map((item) => `<tr><td>${escapeHtml(item.provider)}</td><td>${escapeHtml(item.status)}</td><td>${escapeHtml(item.last_sync_at || "-")}</td><td>${escapeHtml(item.last_error || "-")}</td></tr>`).join(""));
        if (!providerInput?.value && items[0]?.provider) providerInput.value = items[0].provider;
    };
    await render();
    filterForm?.addEventListener("submit", async (event) => {
        event.preventDefault();
        await render();
    });
    resetButton?.addEventListener("click", async () => {
        filterForm?.reset();
        await render();
    });
    updateForm?.addEventListener("submit", async (event) => {
        event.preventDefault();
        try {
            await apiRequest(`/admin/integrations/${encodeURIComponent(providerInput?.value || "")}`, { method: "PATCH", body: JSON.stringify({ endpoint: endpointInput?.value || "" }) });
            showState(true, "Интеграция обновлена.");
            await render();
        } catch (error) {
            showState(false, error.message);
        }
    });
    syncButton?.addEventListener("click", async () => {
        try {
            await apiRequest(`/admin/integrations/${encodeURIComponent(providerInput?.value || "")}/sync`, { method: "POST" });
            showState(true, "Sync запущен.");
            await render();
            if (providerInput?.value) await renderLogs(providerInput.value);
        } catch (error) {
            showState(false, error.message);
        }
    });
    logsButton?.addEventListener("click", async () => {
        try {
            if (!providerInput?.value) return;
            await renderLogs(providerInput.value);
        } catch (error) {
            showState(false, error.message);
        }
    });
}

async function initAdminSettingsPage() {
    try {
        const payload = await apiGet("/admin/settings");
        const data = payload.data || {};
        const seo = document.querySelector("[name=seo_title]");
        const support = document.querySelector("[name=support_email]");
        const notes = document.querySelector("[name=provider_notes]");
        if (seo) seo.value = data.seo_title || "";
        if (support) support.value = data.support_email || "";
        if (notes) notes.value = data.provider_notes || "";
        setHtml("admin-settings-summary", `<div class="entity-card"><strong>${escapeHtml(data.seo_title || "Не задано")}</strong><div class="text-muted">support: ${escapeHtml(data.support_email || "-")}</div></div>`);
        setHtml("admin-settings-notes-preview", `<div class="entity-card"><div class="text-muted">${escapeHtml((data.provider_notes || "").slice(0, 180) || "Заметки отсутствуют")}</div></div>`);
        showNode("admin-settings-error", false);
    } catch (error) {
        showNode("admin-settings-error", true, escapeHtml(error.message || String(error)));
    }
}

async function initAdminMediaPage() {
    try {
        const payload = await apiGet("/admin/media");
        const items = extractList(payload);
        setHtml("admin-media-list", items.map((item) => `<div class="entity-card"><strong>${escapeHtml(item.filename)}</strong><div class="text-muted">${escapeHtml(item.content_type)}</div><div class="text-muted">${escapeHtml(item.url)}</div><div class="mt-2">${escapeHtml(item.size || 0)} байт</div><div class="mt-3 d-flex gap-2"><button class="btn btn-sm btn-outline-danger" type="button" data-media-delete="${escapeHtml(item.id)}">Delete</button></div></div>`).join(""));
        showNode("admin-media-empty", items.length === 0, 'Медиатека пока пуста.');
        showNode("admin-media-error", false);
        document.querySelectorAll("[data-media-delete]").forEach((button) => {
            button.addEventListener("click", async () => {
                try {
                    await apiRequest(`/admin/media/${button.dataset.mediaDelete}`, { method: "DELETE" });
                    await initAdminMediaPage();
                } catch (error) {
                    showNode("admin-media-error", true, escapeHtml(error.message || String(error)));
                }
            });
        });
    } catch (error) {
        setHtml("admin-media-list", "");
        showNode("admin-media-empty", false);
        showNode("admin-media-error", true, escapeHtml(error.message || String(error)));
    }
}

async function initAdminNotificationsPage() {
    const filtersForm = document.getElementById("admin-delivery-log-filters");
    const resetButton = document.getElementById("admin-delivery-log-reset");
    const renderDeliveryLog = async () => {
        const params = new URLSearchParams();
        const notificationType = document.getElementById("admin-delivery-log-type")?.value?.trim() || "";
        const channel = document.getElementById("admin-delivery-log-channel")?.value || "";
        const status = document.getElementById("admin-delivery-log-status")?.value || "";
        if (notificationType) params.set("notification_type", notificationType);
        if (channel) params.set("channel", channel);
        if (status) params.set("status", status);
        const payload = await apiGet(`/admin/notifications/delivery-log${params.toString() ? `?${params.toString()}` : ""}`);
        const items = extractList(payload);
        setHtml("admin-delivery-log", items.map((item) => `<div class="timeline-item"><div class="timeline-time">${escapeHtml(item.created_at)}</div><strong>${escapeHtml(item.notification_type)} · ${escapeHtml(item.channel)}</strong><div class="text-muted">${escapeHtml(item.status)}${item.reason ? ` · ${escapeHtml(item.reason)}` : ""}</div><div class="text-muted">${escapeHtml(item.title)}</div></div>`).join(""));
        showNode("admin-delivery-log-empty", items.length === 0, 'Delivery log пока пуст.');
    };
    const [templatesPayload, historyPayload] = await Promise.all([apiGet("/admin/notifications/templates"), apiGet("/admin/notifications")]);
    const templates = extractList(templatesPayload);
    const history = extractList(historyPayload);
    setHtml("admin-notification-templates", templates.map((item) => `<tr><td>${escapeHtml(item.code)}</td><td>${escapeHtml(item.title)}</td><td>${escapeHtml(item.channel)}</td><td>${escapeHtml(item.is_active ? "активен" : "отключен")}</td><td>${escapeHtml(item.updated_at)}</td></tr>`).join(""));
    setHtml("admin-notification-history", history.map((item) => `<div class="timeline-item"><div class="timeline-time">${escapeHtml(item.created_at)}</div><strong>${escapeHtml(item.title)}</strong><div class="text-muted">${escapeHtml(item.status)} · sent ${escapeHtml(item.sent_count)} · channels ${escapeHtml((item.channels || []).join(", "))}</div></div>`).join(""));
    showNode("admin-notification-templates-empty", templates.length === 0, 'Шаблоны пока недоступны.');
    showNode("admin-notification-history-empty", history.length === 0, 'История отправок пока пуста.');
    await renderDeliveryLog();
    filtersForm?.addEventListener("submit", async (event) => {
        event.preventDefault();
        await renderDeliveryLog();
    });
    resetButton?.addEventListener("click", async () => {
        filtersForm?.reset();
        await renderDeliveryLog();
    });
}

async function initAdminTaxonomyPage(kind) {
    const path = kind === "tags" ? "/admin/tags" : "/admin/news-categories";
    const targetId = kind === "tags" ? "admin-tags-list" : "admin-categories-list";
    const payload = await apiGet(path);
    setHtml(targetId, extractList(payload).map((item) => `<div class="entity-card mt-3"><strong>${escapeHtml(item.name)}</strong><div class="text-muted">${escapeHtml(item.slug)}</div></div>`).join(""));
}

async function initAdminRankingsPage() {
    const payload = await apiGet("/admin/rankings/import-jobs");
    setHtml("admin-ranking-jobs", extractList(payload).map((item) => `<tr><td>${escapeHtml(item.id)}</td><td>${escapeHtml(item.ranking_type)}</td><td>${escapeHtml(item.status)}</td><td>${escapeHtml(item.imported_at)}</td><td>${escapeHtml(item.processed_rows)}</td></tr>`).join(""));
}

async function initAdminLiveOperationsPage() {
    const [livePayload, feedPayload] = await Promise.all([apiGet("/live"), apiGet("/live/feed")]);
    const liveMatches = extractList(livePayload);
    setHtml("admin-live-matches", liveMatches.map((item) => `<div class="entity-card"><strong>${escapeHtml(item.player1_name)} против ${escapeHtml(item.player2_name)}</strong><div class="text-muted">${escapeHtml(item.tournament_name)} · ${escapeHtml(item.round_code || "-")}</div><div class="mt-2">${escapeHtml(item.score_summary || item.status)}</div></div>`).join(""));
    setHtml("admin-live-events", extractList(feedPayload).map((item) => `<div class="timeline-item"><div class="timeline-time">${escapeHtml(item.event_type)}</div><strong>${escapeHtml(item.created_at)}</strong><div class="text-muted">${escapeHtml(JSON.stringify(item.payload_json))}</div></div>`).join(""));
    const matchSelect = document.getElementById("admin-live-match-id");
    const form = document.getElementById("admin-live-event-form");
    if (matchSelect) {
        matchSelect.innerHTML = liveMatches.map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.player1_name)} vs ${escapeHtml(item.player2_name)} · ${escapeHtml(item.tournament_name)}</option>`).join("");
    }
    const updateFormPath = () => {
        if (form && matchSelect?.value) form.dataset.apiPath = `/admin/matches/${matchSelect.value}/events`;
    };
    updateFormPath();
    matchSelect?.addEventListener("change", updateFormPath);
}

async function initAdminUserDetailPage() {
    const userId = getEntityId();
    if (!userId) return;
    const [userPayload, auditPayload] = await Promise.all([apiGet(`/admin/users/${userId}`), apiGet("/admin/audit-logs")]);
    const user = userPayload.data;
    setHtml("admin-user-title", escapeHtml(user.email));
    const email = document.querySelector("[name=email]");
    const username = document.querySelector("[name=username]");
    const role = document.querySelector("[name=role]");
    const status = document.querySelector("[name=status]");
    if (email) email.value = user.email || "";
    if (username) username.value = user.username || "";
    if (role) role.value = user.role || "";
    if (status) status.value = user.status || "";
    setHtml("admin-user-history", extractList(auditPayload).slice(0, 3).map((item) => `<div class="timeline-item"><div class="timeline-time">${escapeHtml(item.created_at)}</div><strong>${escapeHtml(item.action)}</strong><div class="text-muted">${escapeHtml(item.entity_type)} #${escapeHtml(item.entity_id)}</div></div>`).join(""));
}

async function initAdminMatchDetailPage() {
    const matchId = getEntityId();
    if (!matchId) return;
    const payload = await apiGet(`/admin/matches/${matchId}`);
    const match = payload.data;
    setHtml("admin-match-title", escapeHtml(`${match.player1_name} против ${match.player2_name}`));
    const scoreInput = document.querySelector("[name=score_summary]");
    if (scoreInput) scoreInput.value = match.score_summary || "";
    setHtml("admin-match-timeline", (match.timeline || []).map((item) => `<div class="timeline-item"><div class="timeline-time">${escapeHtml(item.event_type)}</div><strong>${escapeHtml(item.created_at)}</strong><div class="text-muted">${escapeHtml(JSON.stringify(item.payload_json))}</div></div>`).join(""));
}

function initTabs() {
    document.querySelectorAll("[data-tab-group]").forEach((group) => {
        const buttons = group.querySelectorAll("[data-tab-target]");
        buttons.forEach((button) => {
            button.addEventListener("click", () => {
                const target = button.getAttribute("data-tab-target");
                buttons.forEach((item) => item.classList.remove("active"));
                button.classList.add("active");
                document.querySelectorAll(`[data-tab-panel="${group.dataset.tabGroup}"]`).forEach((panel) => panel.classList.toggle("d-none", panel.id !== target));
            });
        });
    });
}

function initLoadingButtons() {
    document.querySelectorAll("[data-loading-button]").forEach((button) => {
        button.addEventListener("click", () => {
            const original = button.innerHTML;
            button.disabled = true;
            button.innerHTML = "Загрузка...";
            window.setTimeout(() => { button.disabled = false; button.innerHTML = original; }, 900);
        });
    });
}

function initDemoSearch() {
    const input = document.querySelector("[data-search-demo]");
    const suggestionBox = document.querySelector("[data-search-suggestions]");
    if (!input || !suggestionBox) return;
    input.addEventListener("input", async () => {
        const value = input.value.trim();
        suggestionBox.innerHTML = "";
        if (!value) { suggestionBox.classList.add("d-none"); return; }
        try {
            const payload = await apiGet(`/search/suggestions?q=${encodeURIComponent(value)}`);
            extractList(payload).forEach((item) => {
                const node = document.createElement("button");
                node.type = "button";
                node.className = "list-group-item list-group-item-action";
                node.textContent = `${item.text} · ${item.entity_type}`;
                node.addEventListener("click", () => { input.value = item.text; suggestionBox.classList.add("d-none"); });
                suggestionBox.appendChild(node);
            });
            suggestionBox.classList.toggle("d-none", suggestionBox.childElementCount === 0);
        } catch (_error) { suggestionBox.classList.add("d-none"); }
    });
}

function initLiveTicker() {
    const ticker = document.querySelector("[data-live-ticker]");
    if (!ticker) return;
    apiGet("/live").then((payload) => {
        const frames = extractList(payload).map((item) => `${item.player1_name} против ${item.player2_name}: ${item.score_summary || item.status}`);
        if (frames.length === 0) return;
        let index = 0;
        ticker.textContent = frames[0];
        window.setInterval(() => { index = (index + 1) % frames.length; ticker.textContent = frames[index]; }, 2200);
    }).catch(() => { ticker.textContent = "Лайв-лента недоступна"; });
}

function initFormProtection() {
    document.querySelectorAll("form[data-api-path]").forEach((form) => {
        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            const submit = form.querySelector("[type='submit']");
            if (!submit) return;
            const original = submit.textContent;
            submit.disabled = true;
            submit.textContent = "Сохранение...";
            showFormState(form, true, "");
            try {
                const payload = await apiRequest(form.dataset.apiPath, { method: form.dataset.apiMethod || "POST", body: JSON.stringify(formToJson(form)) });
                showFormState(form, true, payload?.data?.message || payload?.message || "Успешно сохранено.");
            } catch (error) {
                showFormState(form, false, error.message);
            } finally {
                submit.disabled = false;
                submit.textContent = original;
            }
        });
    });
    document.querySelectorAll("[data-api-action]").forEach((button) => {
        button.addEventListener("click", async () => {
            const feedback = button.dataset.targetFeedback ? document.getElementById(button.dataset.targetFeedback) : null;
            const errorNode = button.dataset.targetError ? document.getElementById(button.dataset.targetError) : document.getElementById("match-finalize-error");
            const original = button.textContent;
            button.disabled = true;
            button.textContent = "Обработка...";
            if (feedback) feedback.classList.add("d-none");
            if (errorNode) errorNode.classList.add("d-none");
            try {
                const payload = await apiRequest(button.dataset.apiPath, { method: button.dataset.apiMethod || "POST" });
                if (feedback) {
                    feedback.classList.remove("d-none");
                    feedback.textContent = payload?.data?.message || "Готово.";
                }
            } catch (error) {
                if (errorNode) {
                    errorNode.classList.remove("d-none");
                    errorNode.textContent = error.message;
                }
            } finally {
                button.disabled = false;
                button.textContent = original;
            }
        });
    });
}

async function initPageData() {
    switch (document.body.dataset.page) {
        case "home": await initHomePage(); break;
        case "players-list": await initPlayersListPage(); break;
        case "player-detail": await initPlayerDetailPage(); break;
        case "tournaments-list": await initTournamentsListPage(); break;
        case "tournament-detail": await initTournamentDetailPage(); break;
        case "matches-list": await initMatchesListPage(); break;
        case "match-detail": await initMatchDetailPage(); break;
        case "live-center": await initLiveCenterPage(); break;
        case "rankings": await initRankingsPage(); break;
        case "h2h": await initH2HPage(); break;
        case "news-list": await initNewsListPage(); break;
        case "news-detail": await initNewsDetailPage(); break;
        case "search": await initSearchPage(); break;
        case "account": await initAccountPage(); break;
        case "notifications": await initNotificationsPage(); break;
        case "admin-dashboard": await initAdminDashboard(); break;
        case "admin-users": await initAdminUsersPage(); break;
        case "admin-user-detail": await initAdminUserDetailPage(); break;
        case "admin-players": await initAdminPlayersPage(); break;
        case "admin-tournaments": await initAdminTournamentsPage(); break;
        case "admin-matches": await initAdminMatchesPage(); break;
        case "admin-match-detail": await initAdminMatchDetailPage(); break;
        case "admin-news": await initAdminNewsPage(); break;
        case "admin-integrations": await initAdminIntegrationsPage(); break;
        case "admin-jobs": await initAdminJobsPage(); break;
        case "admin-maintenance": await initAdminMaintenancePage(); break;
        case "admin-audit": await initAdminAuditPage(); break;
        case "admin-media": await initAdminMediaPage(); break;
        case "admin-notifications": await initAdminNotificationsPage(); break;
        case "admin-categories": await initAdminTaxonomyPage("categories"); break;
        case "admin-tags": await initAdminTaxonomyPage("tags"); break;
        case "admin-rankings": await initAdminRankingsPage(); break;
        case "admin-live-operations": await initAdminLiveOperationsPage(); break;
        case "admin-settings": await initAdminSettingsPage(); break;
        default: break;
    }
}

document.addEventListener("DOMContentLoaded", async () => {
    initTabs();
    initLoadingButtons();
    initDemoSearch();
    initLiveTicker();
    initFormProtection();
    try { await initPageData(); } catch (error) { console.error("Page bootstrap failed", error); }
});
