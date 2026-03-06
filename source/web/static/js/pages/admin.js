import { api } from "/static/js/core/api.js";
import { createLiveSocket } from "/static/js/core/websocket.js";
import { debounce, entityId, escapeHtml, extractData, extractList, pageName, qs, queryParam, setHtml, setText, show } from "/static/js/core/utils.js";
import { matchCard, timelineItem } from "/static/js/components/renderers.js";
import { showToast } from "/static/js/core/ui.js";

function actionButton(label, href = "#", type = "ghost") {
    return `<a class="btn btn-sm ${type === "primary" ? "btn-primary" : "btn-ghost-dark"}" href="${escapeHtml(href)}">${escapeHtml(label)}</a>`;
}

async function initDashboard() {
    const [live, news, integrations, audit] = await Promise.all([
        api.live.list(),
        api.admin.news.list().catch(() => ({ data: [] })),
        api.admin.integrations.list().catch(() => ({ data: [] })),
        api.admin.audit.list({ limit: 5 }).catch(() => ({ data: [] })),
    ]);
    setText("admin-live-count", extractList(live).length);
    setText("admin-news-count", extractList(news).filter((item) => item.status !== "published").length);
    setText("admin-integrations-count", extractList(integrations).length);
    setText("admin-jobs-count", "24");
    setHtml("admin-audit-list", extractList(audit).map(timelineItem).join("") || '<div class="state-card">Нет действий.</div>');
    setHtml("admin-integrations-list", extractList(integrations).map((item) => `<div class="notification-item"><strong>${escapeHtml(item.provider)}</strong><div class="text-muted small">${escapeHtml(item.status || "configured")}</div></div>`).join("") || '<div class="state-card">Интеграции еще не настроены.</div>');
}

async function initUsers() {
    const render = async () => {
        const payload = await api.admin.users.list({
            search: qs("#admin-users-search")?.value,
            role: qs("#admin-users-role")?.value,
            status: qs("#admin-users-status")?.value,
        });
        setHtml(
            "admin-users-body",
            extractList(payload)
                .map(
                    (user) => `
                        <tr>
                            <td>${escapeHtml(user.id)}</td>
                            <td>${escapeHtml(user.email || "-")}</td>
                            <td>${escapeHtml(user.username || "-")}</td>
                            <td>${escapeHtml(user.role || "-")}</td>
                            <td>${escapeHtml(user.status || "-")}</td>
                            <td><div class="admin-table-actions">${actionButton("Open", `/admin/users/${user.id}`, "primary")}</div></td>
                        </tr>`,
                )
                .join(""),
        );
    };
    await render();
    qs("#admin-users-filters")?.addEventListener("submit", (event) => {
        event.preventDefault();
        render();
    });
}

async function initUserDetail() {
    const id = entityId();
    if (!id) return;
    const [userPayload, auditPayload] = await Promise.all([
        api.admin.users.detail(id),
        api.admin.audit.list({ user_id: id }).catch(() => ({ data: [] })),
    ]);
    const user = extractData(userPayload);
    setText("admin-user-title", user.username || user.email || `User #${id}`);
    setHtml("admin-user-history", extractList(auditPayload).map(timelineItem).join("") || '<div class="state-card">История отсутствует.</div>');
    qs("#admin-user-set-role")?.addEventListener("click", async () => {
        await api.admin.users.setRole(id, { role: qs("#admin-user-role-control")?.value });
        showToast("Роль обновлена", "success");
    });
    qs("#admin-user-set-status")?.addEventListener("click", async () => {
        await api.admin.users.setStatus(id, { status: qs("#admin-user-status-control")?.value });
        showToast("Статус обновлен", "success");
    });
    qs("#admin-user-delete")?.addEventListener("click", async () => {
        await api.admin.users.delete(id);
        showToast("Пользователь удален", "success");
    });
}

async function initAdminPlayers() {
    const render = async () => {
        const payload = await api.admin.players.list({
            search: qs("#admin-players-search")?.value,
            country_code: qs("#admin-players-country")?.value,
            hand: qs("#admin-players-hand")?.value,
            status: qs("#admin-players-status")?.value,
        });
        setHtml(
            "admin-players-body",
            extractList(payload)
                .map(
                    (player) => `
                        <tr>
                            <td>${escapeHtml(player.full_name || "-")}</td>
                            <td>${escapeHtml(player.country_code || "-")}</td>
                            <td>${escapeHtml(player.current_rank || "-")}</td>
                            <td>${escapeHtml(player.status || "active")}</td>
                            <td><div class="admin-table-actions">${actionButton("Edit", `/admin/players/new?player=${player.id}`, "primary")}</div></td>
                        </tr>`,
                )
                .join(""),
        );
    };
    await render();
    qs("#admin-players-filters")?.addEventListener("input", debounce(render, 260));
    qs("#admin-player-import-form")?.addEventListener("submit", async (event) => {
        event.preventDefault();
        const feedback = qs("#admin-player-import-feedback");
        const errorNode = qs("#admin-player-import-error");
        show(feedback, false);
        show(errorNode, false);
        try {
            const raw = qs("#admin-player-import-json")?.value || "[]";
            const payload = JSON.parse(raw);
            await api.admin.players.import({ players: payload });
            show(feedback, true, "Импорт выполнен.");
            render();
        } catch (error) {
            show(errorNode, true, error.message || "Ошибка импорта.");
        }
    });
}

async function initAdminTournaments() {
    const render = async () => {
        const payload = await api.admin.tournaments.list({
            search: qs("#admin-tournaments-search")?.value,
            category: qs("#admin-tournaments-category")?.value,
            surface: qs("#admin-tournaments-surface")?.value,
            status: qs("#admin-tournaments-status")?.value,
            season_year: qs("#admin-tournaments-season")?.value,
        });
        setHtml(
            "admin-tournaments-body",
            extractList(payload)
                .map(
                    (item) => `
                        <tr>
                            <td>${escapeHtml(item.name)}</td>
                            <td>${escapeHtml(item.category || "-")}</td>
                            <td>${escapeHtml(item.surface || "-")}</td>
                            <td>${escapeHtml(item.status || "-")}</td>
                            <td><div class="admin-table-actions">${actionButton("Edit", `/admin/tournaments/new?tournament=${item.id}`, "primary")}</div></td>
                        </tr>`,
                )
                .join(""),
        );
    };
    await render();
    qs("#admin-tournaments-filters")?.addEventListener("input", debounce(render, 260));
}

async function initAdminMatches() {
    const render = async () => {
        const payload = await api.admin.matches.list({
            search: qs("#admin-matches-search")?.value,
            status: qs("#admin-matches-status")?.value,
        });
        setHtml(
            "admin-matches-body",
            extractList(payload)
                .map(
                    (match) => `
                        <tr>
                            <td>${escapeHtml(match.player1_name)} vs ${escapeHtml(match.player2_name)}</td>
                            <td>${escapeHtml(match.tournament_name || "-")}</td>
                            <td>${escapeHtml(match.status || "-")}</td>
                            <td>${escapeHtml(match.round_code || "-")}</td>
                            <td><div class="admin-table-actions">${actionButton("Detail", `/admin/matches/${match.id}`, "primary")}</div></td>
                        </tr>`,
                )
                .join(""),
        );
    };
    await render();
    qs("#admin-matches-filters")?.addEventListener("input", debounce(render, 260));
    qs("#admin-match-create")?.addEventListener("click", async () => {
        await api.admin.matches.create({
            player1_name: qs("#admin-match-create-player1")?.value,
            player2_name: qs("#admin-match-create-player2")?.value,
            tournament_name: qs("#admin-match-create-tournament")?.value,
            round_code: qs("#admin-match-create-round")?.value,
            status: qs("#admin-match-create-status")?.value,
        });
        showToast("Матч создан", "success");
        render();
    });
}

async function initAdminMatchDetail() {
    const id = entityId();
    if (!id) return;
    const render = async () => {
        const [detailPayload, timelinePayload] = await Promise.all([api.admin.matches.detail(id), api.matches.timeline(id)]);
        const detail = extractData(detailPayload);
        setText("admin-match-title", `${detail.player1_name || ""} vs ${detail.player2_name || ""}`);
        setHtml("admin-match-preview-card", matchCard({ ...detail, slug: detail.slug || "#" }));
        setHtml("admin-match-events", extractList(timelinePayload).map(timelineItem).join("") || '<div class="state-card">Событий пока нет.</div>');
    };
    await render();
    qs("#admin-match-update")?.addEventListener("click", async () => {
        const raw = qs("#admin-match-update-input")?.value || "{}";
        await api.admin.matches.update(id, JSON.parse(raw));
        showToast("Матч обновлен", "success");
        render();
    });
    qs("#admin-match-score-save")?.addEventListener("click", async () => {
        const raw = qs("#admin-match-score-input")?.value || "{}";
        await api.admin.matches.setScore(id, JSON.parse(raw));
        showToast("Score обновлен", "success");
        render();
    });
    qs("#admin-match-stats-save")?.addEventListener("click", async () => {
        const raw = qs("#admin-match-stats-input")?.value || "{}";
        await api.admin.matches.setStats(id, JSON.parse(raw));
        showToast("Stats обновлены", "success");
        render();
    });
    qs("#admin-match-finalize")?.addEventListener("click", async () => {
        await api.admin.matches.finalize(id);
        showToast("Матч финализирован", "success");
        render();
    });
    qs("#admin-match-reopen")?.addEventListener("click", async () => {
        await api.admin.matches.reopen(id);
        showToast("Матч переоткрыт", "success");
        render();
    });
    qs("#admin-match-delete")?.addEventListener("click", async () => {
        await api.admin.matches.delete(id);
        showToast("Матч удален", "success");
    });
    createLiveSocket([`live:match:${id}`], debounce(render, 250));
}

async function initLiveOperations() {
    const render = async () => {
        const payload = await api.live.list();
        const matches = extractList(payload);
        setHtml("admin-live-matches", matches.map(matchCard).join("") || '<div class="state-card">Нет live-матчей.</div>');
        setHtml("admin-live-match-id", `<option value="">Выберите матч</option>${matches.map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.player1_name)} vs ${escapeHtml(item.player2_name)}</option>`).join("")}`);
    };
    await render();
    qs("#admin-live-event-form")?.addEventListener("submit", async (event) => {
        event.preventDefault();
        const matchId = qs("#admin-live-match-id")?.value;
        if (!matchId) {
            showToast("Выберите матч для отправки события", "danger");
            return;
        }
        const payload = {
            event_type: qs("#admin-live-event-form [name='event_type']")?.value,
            set_number: qs("#admin-live-event-form [name='set_number']")?.value,
        };
        try {
            await api.admin.matches.event(matchId, payload);
            showToast("Событие отправлено", "success");
        } catch (error) {
            showToast(error.message || "Ошибка отправки события", "danger");
        }
    });
    createLiveSocket(["live:all"], debounce(render, 280));
}

async function initRankingsImport() {
    const payload = await api.admin.rankings.importJobs().catch(() => ({ data: [] }));
    setHtml(
        "admin-ranking-jobs",
        extractList(payload)
            .map((job) => `<tr><td>${escapeHtml(job.id)}</td><td>${escapeHtml(job.job_type || "ranking_import")}</td><td>${escapeHtml(job.status || "-")}</td><td>${escapeHtml(job.imported_rows || "-")}</td><td>${escapeHtml(job.total_rows || "-")}</td></tr>`)
            .join(""),
    );
}

async function initAdminNews() {
    const payload = await api.admin.news.list().catch(() => ({ data: [] }));
    setHtml(
        "admin-news-body",
        extractList(payload)
            .map((item) => `<tr><td>${escapeHtml(item.title)}</td><td>${escapeHtml(item.status || "-")}</td><td>${escapeHtml(item.category?.name || "-")}</td><td>${escapeHtml(item.published_at || "-")}</td><td><div class="admin-table-actions">${actionButton("Edit", `/admin/news/new?news=${item.id}`, "primary")}</div></td></tr>`)
            .join(""),
    );
}

async function initTaxonomy(type) {
    const payload = type === "categories" ? await api.admin.categories.list().catch(() => ({ data: [] })) : await api.admin.tags.list().catch(() => ({ data: [] }));
    const target = type === "categories" ? "admin-categories-list" : "admin-tags-list";
    setHtml(target, extractList(payload).map((item) => `<div class="notification-item"><strong>${escapeHtml(item.name)}</strong><div class="text-muted small">${escapeHtml(item.slug)}</div></div>`).join("") || '<div class="state-card">Список пуст.</div>');
    if (type === "categories") {
        qs("#admin-category-update")?.addEventListener("click", async () => {
            await api.admin.categories.update(qs("#admin-category-id")?.value, { name: qs("#admin-category-name")?.value, slug: qs("#admin-category-slug")?.value });
            showToast("Категория обновлена", "success");
        });
        qs("#admin-category-delete")?.addEventListener("click", async () => {
            await api.admin.categories.delete(qs("#admin-category-id")?.value);
            showToast("Категория удалена", "success");
        });
    } else {
        qs("#admin-tag-update")?.addEventListener("click", async () => {
            await api.admin.tags.update(qs("#admin-tag-id")?.value, { name: qs("#admin-tag-name")?.value, slug: qs("#admin-tag-slug")?.value });
            showToast("Тег обновлен", "success");
        });
        qs("#admin-tag-delete")?.addEventListener("click", async () => {
            await api.admin.tags.delete(qs("#admin-tag-id")?.value);
            showToast("Тег удален", "success");
        });
    }
}

async function initMedia() {
    setHtml("admin-media-grid", '<div class="state-card">Введите media id, чтобы загрузить или удалить ассет.</div>');
    qs("#admin-media-load")?.addEventListener("click", async () => {
        try {
            const payload = await api.media.detail(qs("#admin-media-id")?.value);
            setHtml("admin-media-grid", `<pre class="mb-0 small">${escapeHtml(JSON.stringify(extractData(payload), null, 2))}</pre>`);
        } catch (error) {
            show("admin-media-error", true, error.message || "Не удалось загрузить media.");
        }
    });
    qs("#admin-media-delete")?.addEventListener("click", async () => {
        try {
            await api.media.delete(qs("#admin-media-id")?.value);
            showToast("Media удалено", "success");
        } catch (error) {
            show("admin-media-error", true, error.message || "Не удалось удалить media.");
        }
    });
}

async function initAdminNotifications() {
    const payload = await api.notifications.list().catch(() => ({ data: [] }));
    setHtml("admin-notifications-list", extractList(payload).map(timelineItem).join("") || '<div class="state-card">Уведомлений пока нет.</div>');
    qs("#admin-notification-test-send")?.addEventListener("click", async () => {
        await api.notifications.test({
            title: qs("#admin-notification-test-title")?.value,
            channel: qs("#admin-notification-test-channel")?.value,
        });
        showToast("Тестовое уведомление отправлено", "success");
    });
}

async function initIntegrations() {
    const payload = await api.admin.integrations.list().catch(() => ({ data: [] }));
    const items = extractList(payload);
    setHtml("admin-integrations-summary", `<div class="admin-note">Подключено провайдеров: <strong>${items.length}</strong></div>`);
    setHtml("admin-integrations-body", items.map((item) => `<tr><td>${escapeHtml(item.provider)}</td><td>${escapeHtml(item.status || "-")}</td><td>${escapeHtml(item.last_synced_at || "-")}</td><td>${escapeHtml(item.last_error || "-")}</td></tr>`).join(""));
    setHtml("admin-integrations-detail", items[0] ? `<div class="admin-note"><strong>${escapeHtml(items[0].provider)}</strong><div class="text-muted mt-2">${escapeHtml(items[0].endpoint || "Endpoint not configured")}</div></div>` : '<div class="state-card">Нет данных.</div>');
    qs("#admin-integrations-save")?.addEventListener("click", async () => {
        const provider = qs("#admin-integrations-target")?.value.trim();
        const endpoint = qs("#admin-integrations-endpoint")?.value.trim();
        if (!provider) {
            show("admin-integrations-error", true, "Укажите provider.");
            return;
        }
        try {
            await api.admin.integrations.update(provider, { endpoint });
            show("admin-integrations-feedback", true, "Настройки интеграции сохранены.");
        } catch (error) {
            show("admin-integrations-error", true, error.message || "Ошибка обновления интеграции.");
        }
    });
    qs("#admin-integrations-sync")?.addEventListener("click", async () => {
        const provider = qs("#admin-integrations-target")?.value.trim() || items[0]?.provider;
        if (!provider) return;
        try {
            await api.admin.integrations.sync(provider);
            show("admin-integrations-feedback", true, `Sync запущен для ${provider}.`);
        } catch (error) {
            show("admin-integrations-error", true, error.message || "Sync завершился ошибкой.");
        }
    });
    qs("#admin-integrations-load-logs")?.addEventListener("click", async () => {
        const provider = qs("#admin-integrations-target")?.value.trim() || items[0]?.provider;
        if (!provider) return;
        try {
            const logsPayload = await api.admin.integrations.logs(provider);
            const logs = extractList(logsPayload);
            setHtml("admin-integrations-logs", logs.length ? logs.map(timelineItem).join("") : '<div class="state-card">Логи не найдены.</div>');
        } catch (error) {
            show("admin-integrations-error", true, error.message || "Не удалось загрузить логи.");
        }
    });
}

async function initAudit() {
    const payload = await api.admin.audit.list({ limit: 20 }).catch(() => ({ data: [] }));
    const items = extractList(payload);
    setHtml("admin-audit-summary", `<div class="admin-note">Последних записей: <strong>${items.length}</strong></div>`);
    setHtml("admin-audit-body", items.map((item) => `<tr data-audit-row="${escapeHtml(item.id || "")}"><td>${escapeHtml(item.action || "-")}</td><td>${escapeHtml(item.entity_type || "-")}</td><td>${escapeHtml(item.user_id || "-")}</td><td>${escapeHtml(item.created_at || "-")}</td></tr>`).join(""));
    document.querySelectorAll("[data-audit-row]").forEach((row) => row.addEventListener("click", async () => {
        const detailPayload = await api.admin.audit.detail(row.dataset.auditRow).catch(() => ({ data: {} }));
        setHtml("admin-audit-detail", `<pre class="mb-0 small">${escapeHtml(JSON.stringify(extractData(detailPayload), null, 2))}</pre>`);
    }));
}

async function initSettings() {
    try {
        const payload = await api.admin.settings.get();
        const settings = extractData(payload);
        setHtml("admin-settings-summary", `<div class="admin-note"><strong>${escapeHtml(settings.seo_title || "Makhachkala Open")}</strong><div class="text-muted mt-2">${escapeHtml(settings.support_email || "")}</div></div>`);
        setHtml("admin-settings-notes-preview", `<div class="admin-note">${escapeHtml(settings.provider_notes || "Системные заметки отсутствуют.")}</div>`);
        setHtml("admin-settings-storage", `<div class="admin-note">Runtime store active. API ready for ` + escapeHtml("PATCH /admin/settings") + `.</div>`);
    } catch (error) {
        show("admin-settings-error", true, error.message || "Ошибка загрузки настроек.");
    }
}

async function initAdminPlayerForm() {
    const id = queryParam("player");
    if (!id) return;
    const detailPayload = await api.admin.players.detail(id).catch(() => ({ data: {} }));
    const player = extractData(detailPayload);
    setText("admin-player-form-meta", `Edit mode • player #${id}`);
    qs("#admin-player-load-detail")?.addEventListener("click", async () => {
        const payload = await api.admin.players.detail(id);
        setText("admin-player-form-meta", `Loaded • ${extractData(payload).full_name || `player #${id}`}`);
    });
    qs("#admin-player-update")?.addEventListener("click", async () => {
        await api.admin.players.update(id, {
            full_name: qs("[name='full_name']")?.value || player.full_name,
            slug: qs("[name='slug']")?.value || player.slug,
            country_code: qs("[name='country_code']")?.value || player.country_code,
            hand: qs("[name='hand']")?.value || player.hand,
            current_rank: qs("[name='current_rank']")?.value || player.current_rank,
            photo_url: qs("[name='photo_url']")?.value || player.photo_url,
            biography: qs("[name='biography']")?.value || player.biography,
        });
        showToast("Игрок обновлен", "success");
    });
    qs("#admin-player-photo-save")?.addEventListener("click", async () => {
        await api.admin.players.photo(id, { photo_url: qs("#admin-player-photo-url")?.value });
        showToast("Фото обновлено", "success");
    });
    qs("#admin-player-recalc")?.addEventListener("click", async () => {
        await api.admin.players.recalculateStats(id);
        showToast("Статистика пересчитана", "success");
    });
    qs("#admin-player-delete")?.addEventListener("click", async () => {
        await api.admin.players.delete(id);
        showToast("Игрок удален", "success");
    });
}

async function initAdminTournamentForm() {
    const id = queryParam("tournament");
    if (!id) return;
    const detailPayload = await api.admin.tournaments.detail(id).catch(() => ({ data: {} }));
    const tournament = extractData(detailPayload);
    setText("admin-tournament-form-meta", `Edit mode • tournament #${id}`);
    qs("#admin-tournament-load-detail")?.addEventListener("click", async () => {
        const payload = await api.admin.tournaments.detail(id);
        setText("admin-tournament-form-meta", `Loaded • ${extractData(payload).name || `tournament #${id}`}`);
    });
    qs("#admin-tournament-update")?.addEventListener("click", async () => {
        await api.admin.tournaments.update(id, {
            name: qs("[name='name']")?.value || tournament.name,
            slug: qs("[name='slug']")?.value || tournament.slug,
            category: qs("[name='category']")?.value || tournament.category,
            surface: qs("[name='surface']")?.value || tournament.surface,
            season_year: qs("[name='season_year']")?.value || tournament.season_year,
            city: qs("[name='city']")?.value || tournament.city,
            country_code: qs("[name='country_code']")?.value || tournament.country_code,
            description: qs("[name='description']")?.value || tournament.description,
        });
        showToast("Турнир обновлен", "success");
    });
    qs("#admin-tournament-generate-draw")?.addEventListener("click", async () => {
        await api.admin.tournaments.generateDraw(id);
        showToast("Draw сгенерирован", "success");
    });
    qs("#admin-tournament-publish")?.addEventListener("click", async () => {
        await api.admin.tournaments.publish(id);
        showToast("Турнир опубликован", "success");
    });
    qs("#admin-tournament-delete")?.addEventListener("click", async () => {
        await api.admin.tournaments.delete(id);
        showToast("Турнир удален", "success");
    });
}

async function initAdminNewsForm() {
    const id = queryParam("news");
    if (!id) return;
    const detailPayload = await api.admin.news.detail(id).catch(() => ({ data: {} }));
    const article = extractData(detailPayload);
    setText("admin-news-form-meta", `Edit mode • news #${id}`);
    qs("#admin-news-load-detail")?.addEventListener("click", async () => {
        const payload = await api.admin.news.detail(id);
        setText("admin-news-form-meta", `Loaded • ${extractData(payload).title || `news #${id}`}`);
    });
    qs("#admin-news-update")?.addEventListener("click", async () => {
        await api.admin.news.update(id, {
            title: qs("[name='title']")?.value || article.title,
            slug: qs("[name='slug']")?.value || article.slug,
            subtitle: qs("[name='subtitle']")?.value || article.subtitle,
            seo_title: qs("[name='seo_title']")?.value || article.seo_title,
            lead: qs("[name='lead']")?.value || article.lead,
            content: qs("[name='content']")?.value || article.content,
        });
        showToast("Новость обновлена", "success");
    });
    qs("#admin-news-set-status")?.addEventListener("click", async () => {
        await api.admin.news.setStatus(id, { status: qs("#admin-news-status-control")?.value });
        showToast("Статус обновлен", "success");
    });
    qs("#admin-news-publish")?.addEventListener("click", async () => {
        await api.admin.news.publish(id);
        showToast("Новость опубликована", "success");
    });
    qs("#admin-news-schedule")?.addEventListener("click", async () => {
        await api.admin.news.schedule(id, { scheduled_at: qs("#admin-news-schedule-at")?.value });
        showToast("Публикация запланирована", "success");
    });
    qs("#admin-news-cover")?.addEventListener("click", async () => {
        await api.admin.news.cover(id, { cover_image_url: qs("#admin-news-cover-url")?.value });
        showToast("Обложка обновлена", "success");
    });
    qs("#admin-news-tags-save")?.addEventListener("click", async () => {
        await api.admin.news.tags(id, { tag_ids: String(qs("#admin-news-tags-input")?.value || "").split(",").map((item) => item.trim()).filter(Boolean) });
        showToast("Теги обновлены", "success");
    });
    qs("#admin-news-delete")?.addEventListener("click", async () => {
        await api.admin.news.delete(id);
        showToast("Новость удалена", "success");
    });
}

export async function initAdminPages() {
    const current = pageName();
    if (!current.startsWith("admin-")) return;
    const routes = {
        "admin-dashboard": initDashboard,
        "admin-users": initUsers,
        "admin-user-detail": initUserDetail,
        "admin-players": initAdminPlayers,
        "admin-player-form": initAdminPlayerForm,
        "admin-tournaments": initAdminTournaments,
        "admin-tournament-form": initAdminTournamentForm,
        "admin-matches": initAdminMatches,
        "admin-match-detail": initAdminMatchDetail,
        "admin-live-operations": initLiveOperations,
        "admin-rankings": initRankingsImport,
        "admin-news": initAdminNews,
        "admin-news-form": initAdminNewsForm,
        "admin-categories": () => initTaxonomy("categories"),
        "admin-tags": () => initTaxonomy("tags"),
        "admin-media": initMedia,
        "admin-notifications": initAdminNotifications,
        "admin-integrations": initIntegrations,
        "admin-audit": initAudit,
        "admin-settings": initSettings,
    };
    const init = routes[current];
    if (init) await init();
}
