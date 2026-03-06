import { escapeHtml, formatDate, initials, statusLabel } from "/static/js/core/utils.js";

function statusClass(status) {
    const value = String(status || "").toLowerCase();
    return `status-pill status-${escapeHtml(value)}`;
}

function playerFlag(countryCode) {
    return countryCode ? `<span class="badge-soft">${escapeHtml(countryCode)}</span>` : "";
}

export function playerCard(player) {
    return `
        <a class="entity-card fade-up" href="/players/${escapeHtml(player.slug)}">
            <div class="entity-card__head">
                <div class="d-flex gap-3">
                    ${player.photo_url ? `<img class="player-avatar" src="${escapeHtml(player.photo_url)}" alt="${escapeHtml(player.full_name)}">` : `<span class="player-avatar__fallback">${escapeHtml(initials(player.full_name))}</span>`}
                    <div>
                        <div class="entity-card__eyebrow">Player profile</div>
                        <h3 class="entity-card__title">${escapeHtml(player.full_name)}</h3>
                        <div class="entity-card__meta">Rank #${escapeHtml(player.current_rank ?? "-")} • ${escapeHtml(player.country_name || player.country_code || "")}</div>
                    </div>
                </div>
                ${playerFlag(player.country_code)}
            </div>
            <div class="entity-card__summary mt-3">${escapeHtml(player.biography || "Сезонная форма, рейтинг, очки и ближайшие матчи.")}</div>
            <div class="d-flex flex-wrap gap-2 mt-3">
                <span class="badge-soft">Pts ${escapeHtml(player.current_points ?? "-")}</span>
                <span class="badge-soft">${escapeHtml(statusLabel(player.hand || "right-handed"))}</span>
                <span class="badge-soft">${escapeHtml(statusLabel(player.backhand || "two handed"))}</span>
            </div>
        </a>`;
}

export function tournamentCard(tournament) {
    return `
        <a class="entity-card fade-up" href="/tournaments/${escapeHtml(tournament.slug)}">
            <div class="entity-card__row">
                <div class="entity-card__eyebrow">${escapeHtml(statusLabel(tournament.category || "Tournament"))}</div>
                <span class="${statusClass(tournament.status || "scheduled")}">${escapeHtml(statusLabel(tournament.status || "scheduled"))}</span>
            </div>
            <h3 class="entity-card__title">${escapeHtml(tournament.name)}</h3>
            <div class="entity-card__meta">${escapeHtml(tournament.city || "")}${tournament.city && tournament.country_code ? ", " : ""}${escapeHtml(tournament.country_code || "")}</div>
            <div class="d-flex flex-wrap gap-2 mt-3">
                <span class="badge-soft">${escapeHtml(statusLabel(tournament.surface || "hard"))}</span>
                <span class="badge-soft">${escapeHtml(tournament.start_date || "")}</span>
                <span class="badge-soft">${escapeHtml(tournament.end_date || "")}</span>
            </div>
        </a>`;
}

export function matchCard(match) {
    const live = String(match.status || "").toLowerCase() === "live";
    return `
        <a class="entity-card fade-up" href="/matches/${escapeHtml(match.slug)}">
            <div class="entity-card__row">
                <div class="entity-card__eyebrow">${escapeHtml(match.tournament_name || "Match center")}</div>
                <span class="${live ? "badge-live" : statusClass(match.status)}">${escapeHtml(statusLabel(match.status || "scheduled"))}</span>
            </div>
            <h3 class="entity-card__title">${escapeHtml(match.player1_name)} vs ${escapeHtml(match.player2_name)}</h3>
            <div class="entity-card__meta">${escapeHtml(match.round_code || "Main draw")} • ${escapeHtml(formatDate(match.scheduled_at, { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" }))}</div>
            <div class="d-flex justify-content-between align-items-center mt-3">
                <div class="badge-soft">H2H ${escapeHtml(match.h2h_summary || "Preview")}</div>
                <strong>${escapeHtml(match.score_summary || match.current_score || "Awaiting first serve")}</strong>
            </div>
        </a>`;
}

export function newsCard(article) {
    return `
        <a class="entity-card editorial-card fade-up" href="/news/${escapeHtml(article.slug)}">
            <div class="article-cover mb-3"></div>
            <div class="entity-card__eyebrow">${escapeHtml(article.category?.name || article.status || "News")}</div>
            <h3 class="entity-card__title">${escapeHtml(article.title)}</h3>
            <div class="entity-card__summary">${escapeHtml(article.lead || article.subtitle || "Редакционная аналитика, live context и быстрые инсайты по матчу.")}</div>
            <div class="d-flex justify-content-between align-items-center mt-3">
                <span class="badge-soft">${escapeHtml(formatDate(article.published_at, { day: "2-digit", month: "short" }))}</span>
                <span class="text-muted small">${escapeHtml(article.read_time || "3 min read")}</span>
            </div>
        </a>`;
}

export function notificationCard(item) {
    return `
        <div class="notification-item ${item.read_at ? "" : "is-unread"}">
            <div class="d-flex justify-content-between gap-2">
                <strong>${escapeHtml(item.title || item.type || "Notification")}</strong>
                <span class="text-muted small">${escapeHtml(formatDate(item.created_at))}</span>
            </div>
            <div class="text-muted small mt-2">${escapeHtml(item.body || "")}</div>
        </div>`;
}

export function timelineItem(item) {
    const payload = typeof item.payload_json === "object" ? JSON.stringify(item.payload_json) : item.payload_json;
    return `
        <article class="timeline-item">
            <div class="timeline-item__time">${escapeHtml(item.event_type || item.type || "Event")}</div>
            <strong>${escapeHtml(item.title || item.label || "Live update")}</strong>
            <div class="text-muted small mt-2">${escapeHtml(payload || item.description || "")}</div>
        </article>`;
}

export function rankingRow(item) {
    const movement = Number(item.movement || 0);
    const movementClass = movement > 0 ? "up" : movement < 0 ? "down" : "flat";
    const movementLabel = movement > 0 ? `+${movement}` : `${movement}`;
    return `
        <tr>
            <td>${escapeHtml(item.rank_position ?? item.rank ?? "-")}</td>
            <td><span class="rank-move ${movementClass}">${escapeHtml(movementLabel)}</span></td>
            <td>${escapeHtml(item.player_name || item.full_name || "-")}</td>
            <td>${escapeHtml(item.country_code || "-")}</td>
            <td>${escapeHtml(item.points ?? "-")}</td>
        </tr>`;
}

export function statPair(label, leftValue, rightValue) {
    return `
        <div class="stats-pair">
            <div class="stats-pair__value">${escapeHtml(leftValue ?? "-")}</div>
            <div class="text-muted small text-center">${escapeHtml(label)}</div>
            <div class="stats-pair__value is-right">${escapeHtml(rightValue ?? "-")}</div>
        </div>`;
}

export function scoreboard(detail, score = detail.score || {}) {
    const sets = Array.isArray(score.sets) ? score.sets : [];
    const serveTarget = score.server || detail.serving_player || "";
    const setValues = (index) =>
        Array.from({ length: 3 }, (_item, setIndex) => {
            const set = String(sets[setIndex] || "").split("-");
            return escapeHtml(set[index] || "-");
        }).join("");

    return `
        <div class="scoreboard-card fade-up">
            <div class="d-flex flex-wrap justify-content-between gap-3 align-items-center mb-3">
                <div>
                    <div class="section-kicker">${escapeHtml(detail.tournament_name || "Live center")}</div>
                    <h1 class="section-title mt-2">${escapeHtml(detail.player1_name)} vs ${escapeHtml(detail.player2_name)}</h1>
                    <div class="text-muted mt-1">${escapeHtml(detail.round_code || "Main draw")} • ${escapeHtml(formatDate(detail.scheduled_at))}</div>
                </div>
                <span class="${String(detail.status).toLowerCase() === "live" ? "badge-live" : statusClass(detail.status)}">${escapeHtml(statusLabel(detail.status || "scheduled"))}</span>
            </div>
            <div class="scoreboard-card__grid">
                <div class="d-grid gap-2">
                    <div class="scoreboard-player ${serveTarget === detail.player1_name ? "is-serving" : ""}">
                        <div class="scoreboard-player__name"><span class="scoreboard-player__flag">${escapeHtml(detail.player1_country_flag || "🎾")}</span>${escapeHtml(detail.player1_name)}</div>
                        ${Array.from({ length: 3 }, (_item, index) => `<div class="scoreboard-player__set">${escapeHtml(String(sets[index] || "").split("-")[0] || "-")}</div>`).join("")}
                        <div class="scoreboard-player__game">${escapeHtml(score.player1_game || score.current_game?.split("-")[0] || "-")}</div>
                    </div>
                    <div class="scoreboard-player ${serveTarget === detail.player2_name ? "is-serving" : ""}">
                        <div class="scoreboard-player__name"><span class="scoreboard-player__flag">${escapeHtml(detail.player2_country_flag || "🎾")}</span>${escapeHtml(detail.player2_name)}</div>
                        ${Array.from({ length: 3 }, (_item, index) => `<div class="scoreboard-player__set">${escapeHtml(String(sets[index] || "").split("-")[1] || "-")}</div>`).join("")}
                        <div class="scoreboard-player__game">${escapeHtml(score.player2_game || score.current_game?.split("-")[1] || "-")}</div>
                    </div>
                </div>
                <div class="glass-card rounded-4 p-3 h-100">
                    <div class="section-kicker">Match pulse</div>
                    <div class="metric-value mt-2">${escapeHtml(score.current_game || detail.score_summary || "Pre-match")}</div>
                    <div class="text-muted mt-2">Server: ${escapeHtml(serveTarget || "TBD")}</div>
                    <div class="d-flex flex-wrap gap-2 mt-3">
                        <span class="badge-soft">Court ${escapeHtml(detail.court_name || "-")}</span>
                        <span class="badge-soft">Rank ${escapeHtml(detail.player1_rank || "-")} / ${escapeHtml(detail.player2_rank || "-")}</span>
                    </div>
                </div>
            </div>
        </div>`;
}
