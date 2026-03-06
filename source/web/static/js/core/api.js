import { toQuery } from "/static/js/core/utils.js";

const API_BASE = document.body.dataset.apiBase || "/api/v1";

async function request(path, options = {}) {
    const response = await fetch(`${API_BASE}${path}`, {
        headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
            ...(options.headers || {}),
        },
        credentials: "same-origin",
        ...options,
    });

    const text = await response.text();
    let payload = null;
    try {
        payload = text ? JSON.parse(text) : null;
    } catch (_error) {
        payload = null;
    }

    if (!response.ok) {
        const message = payload?.errors?.[0]?.message || payload?.detail || `HTTP ${response.status}`;
        throw new Error(message);
    }

    return payload;
}

function get(path, params) {
    return request(`${path}${toQuery(params)}`);
}

function post(path, body) {
    return request(path, { method: "POST", body: JSON.stringify(body ?? {}) });
}

function patch(path, body) {
    return request(path, { method: "PATCH", body: JSON.stringify(body ?? {}) });
}

function del(path) {
    return request(path, { method: "DELETE" });
}

export const api = {
    request,
    get,
    post,
    patch,
    delete: del,
    auth: {
        register: (body) => post("/auth/register", body),
        login: (body) => post("/auth/login", body),
        refresh: (body) => post("/auth/refresh", body),
        logout: (body) => post("/auth/logout", body),
        forgotPassword: (body) => post("/auth/forgot-password", body),
        resetPassword: (body) => post("/auth/reset-password", body),
        verifyEmail: (body) => post("/auth/verify-email", body),
        me: () => get("/auth/me"),
    },
    users: {
        me: () => get("/users/me"),
        updateMe: (body) => patch("/users/me", body),
        updatePassword: (body) => patch("/users/me/password", body),
        favorites: () => get("/users/me/favorites"),
        addFavorite: (body) => post("/users/me/favorites", body),
        removeFavorite: (favoriteId) => del(`/users/me/favorites/${favoriteId}`),
        subscriptions: () => get("/users/me/subscriptions"),
        addSubscription: (body) => post("/users/me/subscriptions", body),
        updateSubscription: (id, body) => patch(`/users/me/subscriptions/${id}`, body),
        removeSubscription: (id) => del(`/users/me/subscriptions/${id}`),
        notifications: () => get("/users/me/notifications"),
        readNotification: (id) => patch(`/users/me/notifications/${id}/read`, {}),
        readAllNotifications: () => patch("/users/me/notifications/read-all", {}),
    },
    players: {
        list: (params) => get("/players", params),
        detail: (id) => get(`/players/${id}`),
        stats: (id) => get(`/players/${id}/stats`),
        matches: (id) => get(`/players/${id}/matches`),
        rankingHistory: (id) => get(`/players/${id}/ranking-history`),
        titles: (id) => get(`/players/${id}/titles`),
        news: (id) => get(`/players/${id}/news`),
        upcoming: (id) => get(`/players/${id}/upcoming-matches`),
        compare: (params) => get("/players/compare", params),
        h2h: (params) => get("/players/h2h", params),
    },
    tournaments: {
        list: (params) => get("/tournaments", params),
        detail: (id) => get(`/tournaments/${id}`),
        matches: (id) => get(`/tournaments/${id}/matches`),
        draw: (id) => get(`/tournaments/${id}/draw`),
        players: (id) => get(`/tournaments/${id}/players`),
        champions: (id) => get(`/tournaments/${id}/champions`),
        news: (id) => get(`/tournaments/${id}/news`),
        calendar: (params) => get("/tournaments/calendar", params),
    },
    matches: {
        list: (params) => get("/matches", params),
        detail: (id) => get(`/matches/${id}`),
        score: (id) => get(`/matches/${id}/score`),
        stats: (id) => get(`/matches/${id}/stats`),
        timeline: (id) => get(`/matches/${id}/timeline`),
        h2h: (id) => get(`/matches/${id}/h2h`),
        preview: (id) => get(`/matches/${id}/preview`),
        pointByPoint: (id) => get(`/matches/${id}/point-by-point`),
        upcoming: (params) => get("/matches/upcoming", params),
        results: (params) => get("/matches/results", params),
    },
    live: {
        list: () => get("/live"),
        detail: (matchId) => get(`/live/${matchId}`),
        feed: () => get("/live/feed"),
    },
    rankings: {
        list: (params) => get("/rankings", params),
        current: (params) => get("/rankings/current", params),
        history: (rankingType, params) => get(`/rankings/${rankingType}/history`, params),
        player: (playerId) => get(`/rankings/player/${playerId}`),
        race: (params) => get("/rankings/race", params),
    },
    news: {
        list: (params) => get("/news", params),
        detail: (slug) => get(`/news/${slug}`),
        categories: () => get("/news/categories"),
        tags: () => get("/news/tags"),
        featured: () => get("/news/featured"),
        related: (params) => get("/news/related", params),
    },
    search: {
        query: (params) => get("/search", params),
        suggestions: (params) => get("/search/suggestions", params),
    },
    notifications: {
        list: () => get("/notifications"),
        unreadCount: () => get("/notifications/unread-count"),
        read: (id) => patch(`/notifications/${id}/read`, {}),
        readAll: () => patch("/notifications/read-all", {}),
        test: (body) => post("/notifications/test", body),
    },
    media: {
        upload: (body) => post("/media/upload", body),
        detail: (id) => get(`/media/${id}`),
        delete: (id) => del(`/media/${id}`),
    },
    admin: {
        users: {
            list: (params) => get("/admin/users", params),
            detail: (id) => get(`/admin/users/${id}`),
            update: (id, body) => patch(`/admin/users/${id}`, body),
            setStatus: (id, body) => patch(`/admin/users/${id}/status`, body),
            setRole: (id, body) => patch(`/admin/users/${id}/role`, body),
            delete: (id) => del(`/admin/users/${id}`),
        },
        players: {
            list: (params) => get("/admin/players", params),
            create: (body) => post("/admin/players", body),
            detail: (id) => get(`/admin/players/${id}`),
            update: (id, body) => patch(`/admin/players/${id}`, body),
            delete: (id) => del(`/admin/players/${id}`),
            import: (body) => post("/admin/players/import", body),
            photo: (id, body) => post(`/admin/players/${id}/photo`, body),
            recalculateStats: (id) => post(`/admin/players/${id}/recalculate-stats`, {}),
        },
        tournaments: {
            list: (params) => get("/admin/tournaments", params),
            create: (body) => post("/admin/tournaments", body),
            detail: (id) => get(`/admin/tournaments/${id}`),
            update: (id, body) => patch(`/admin/tournaments/${id}`, body),
            delete: (id) => del(`/admin/tournaments/${id}`),
            generateDraw: (id) => post(`/admin/tournaments/${id}/draw/generate`, {}),
            publish: (id) => post(`/admin/tournaments/${id}/publish`, {}),
        },
        matches: {
            list: (params) => get("/admin/matches", params),
            create: (body) => post("/admin/matches", body),
            detail: (id) => get(`/admin/matches/${id}`),
            update: (id, body) => patch(`/admin/matches/${id}`, body),
            delete: (id) => del(`/admin/matches/${id}`),
            setStatus: (id, body) => patch(`/admin/matches/${id}/status`, body),
            setScore: (id, body) => patch(`/admin/matches/${id}/score`, body),
            setStats: (id, body) => patch(`/admin/matches/${id}/stats`, body),
            event: (id, body) => post(`/admin/matches/${id}/events`, body),
            finalize: (id) => post(`/admin/matches/${id}/finalize`, {}),
            reopen: (id) => post(`/admin/matches/${id}/reopen`, {}),
        },
        rankings: {
            importJobs: () => get("/admin/rankings/import-jobs"),
            import: (body) => post("/admin/rankings/import", body),
            recalculateMovements: () => post("/admin/rankings/recalculate-movements", {}),
        },
        news: {
            list: (params) => get("/admin/news", params),
            create: (body) => post("/admin/news", body),
            detail: (id) => get(`/admin/news/${id}`),
            update: (id, body) => patch(`/admin/news/${id}`, body),
            delete: (id) => del(`/admin/news/${id}`),
            setStatus: (id, body) => patch(`/admin/news/${id}/status`, body),
            publish: (id) => post(`/admin/news/${id}/publish`, {}),
            schedule: (id, body) => post(`/admin/news/${id}/schedule`, body),
            cover: (id, body) => post(`/admin/news/${id}/cover`, body),
            tags: (id, body) => post(`/admin/news/${id}/tags`, body),
        },
        categories: {
            list: () => get("/admin/news-categories"),
            create: (body) => post("/admin/news-categories", body),
            update: (id, body) => patch(`/admin/news-categories/${id}`, body),
            delete: (id) => del(`/admin/news-categories/${id}`),
        },
        tags: {
            list: () => get("/admin/tags"),
            create: (body) => post("/admin/tags", body),
            update: (id, body) => patch(`/admin/tags/${id}`, body),
            delete: (id) => del(`/admin/tags/${id}`),
        },
        integrations: {
            list: () => get("/admin/integrations"),
            update: (provider, body) => patch(`/admin/integrations/${provider}`, body),
            sync: (provider) => post(`/admin/integrations/${provider}/sync`, {}),
            logs: (provider) => get(`/admin/integrations/${provider}/logs`),
        },
        audit: {
            list: (params) => get("/admin/audit-logs", params),
            detail: (id) => get(`/admin/audit-logs/${id}`),
        },
        settings: {
            get: () => get("/admin/settings"),
            update: (body) => patch("/admin/settings", body),
        },
    },
};

export function formToJson(form) {
    const payload = {};
    new FormData(form).forEach((value, key) => {
        if (value === "") return;
        if (payload[key] !== undefined) {
            payload[key] = [].concat(payload[key], value);
            return;
        }
        payload[key] = value;
    });
    form.querySelectorAll("input[type='checkbox']").forEach((input) => {
        payload[input.name] = input.checked;
    });
    return payload;
}
