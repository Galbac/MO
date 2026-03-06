import { api } from "/static/js/core/api.js";
import { escapeHtml, qsa, setHtml, setText } from "/static/js/core/utils.js";

function renderCompact(items) {
    return items
        .slice(0, 5)
        .map(
            (item) => `
                <div class="notification-item ${item.read_at ? "" : "is-unread"}">
                    <div class="d-flex justify-content-between gap-2">
                        <strong>${escapeHtml(item.title || item.type || "Уведомление")}</strong>
                        <span class="text-muted small">${escapeHtml(item.created_at || "")}</span>
                    </div>
                    <div class="text-muted small mt-1">${escapeHtml(item.body || "")}</div>
                </div>`,
        )
        .join("");
}

export async function initNotificationsUI() {
    const badge = document.getElementById("notifications-unread-count");
    const dropdown = document.getElementById("notifications-dropdown-list");
    const pageCounter = document.getElementById("notifications-count");

    try {
        const [countPayload, listPayload] = await Promise.all([
            api.notifications.unreadCount().catch(() => ({ data: { unread_count: 0 } })),
            api.notifications.list().catch(() => ({ data: [] })),
        ]);

        const unreadCount = countPayload?.data?.unread_count ?? 0;
        const notifications = Array.isArray(listPayload?.data) ? listPayload.data : [];

        if (badge) {
            badge.textContent = String(unreadCount);
            badge.classList.toggle("d-none", unreadCount === 0);
        }
        if (dropdown) {
            setHtml(dropdown, notifications.length ? renderCompact(notifications) : '<div class="notification-item">Пока пусто.</div>');
        }
        if (pageCounter) {
            setText(pageCounter, unreadCount > 0 ? `Непрочитанных: ${unreadCount}` : "Все уведомления прочитаны.");
        }
    } catch (_error) {
        qsa("[data-notifications-fallback]").forEach((node) => {
            node.textContent = "Уведомления недоступны";
        });
    }
}
