import { api } from "/static/js/core/api.js";
import { qsa, show } from "/static/js/core/utils.js";
import { showToast } from "/static/js/core/ui.js";

function initFavoriteButtons() {
    qsa("[data-favorite-button]").forEach((button) => {
        button.addEventListener("click", async () => {
            const entityType = button.dataset.entityType;
            const entityId = button.dataset.entityId;
            try {
                await api.users.addFavorite({ entity_type: entityType, entity_id: entityId });
                button.classList.add("active");
                showToast("Добавлено в избранное", "success");
            } catch (error) {
                showToast(error.message || "Не удалось добавить в избранное", "danger");
            }
        });
    });
}

function initSubscriptionButtons() {
    qsa("[data-subscribe-button]").forEach((button) => {
        button.addEventListener("click", async () => {
            try {
                await api.users.addSubscription({
                    entity_type: button.dataset.entityType,
                    entity_id: button.dataset.entityId,
                    channel: button.dataset.channel || "web",
                });
                button.classList.add("active");
                showToast("Подписка оформлена", "success");
            } catch (error) {
                showToast(error.message || "Не удалось оформить подписку", "danger");
            }
        });
    });
}

export function initAuth() {
    initFavoriteButtons();
    initSubscriptionButtons();

    qsa("[data-auth-required]").forEach((node) => {
        api.auth.me()
            .then(() => show(node, true))
            .catch(() => show(node, false));
    });
}
