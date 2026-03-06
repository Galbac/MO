import { api, formToJson } from "/static/js/core/api.js";
import { escapeHtml, qs, qsa, setText, show } from "/static/js/core/utils.js";

function activateTabs() {
    qsa("[data-tab-group]").forEach((group) => {
        const buttons = qsa("[data-tab-target]", group);
        buttons.forEach((button) => {
            button.addEventListener("click", () => {
                const target = button.dataset.tabTarget;
                buttons.forEach((item) => item.classList.toggle("is-active", item === button));
                const scope = group.dataset.tabGroup;
                qsa(`[data-tab-panel="${scope}"]`).forEach((panel) => {
                    panel.classList.toggle("d-none", panel.id !== target);
                });
            });
        });
    });
}

function initActiveNav() {
    const path = window.location.pathname;
    qsa("[data-nav-link]").forEach((link) => {
        const href = link.getAttribute("href");
        const active = href === "/" ? path === "/" : path === href || path.startsWith(`${href}/`);
        link.classList.toggle("is-active", active);
    });
}

function initForms() {
    qsa("form[data-api-path]").forEach((form) => {
        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            const feedback = qs("[data-form-feedback]", form);
            const error = qs("[data-form-error]", form);
            show(feedback, false);
            show(error, false);
            const button = qs("button[type='submit']", form);
            if (button) button.disabled = true;

            try {
                const method = (form.dataset.apiMethod || "POST").toLowerCase();
                const path = form.dataset.apiPath;
                const payload = formToJson(form);
                if (method === "post") await api.post(path, payload);
                else if (method === "patch") await api.patch(path, payload);
                else if (method === "delete") await api.delete(path);
                show(feedback, true, feedback?.textContent || "Готово");
            } catch (submitError) {
                show(error, true, submitError.message || "Ошибка запроса");
            } finally {
                if (button) button.disabled = false;
            }
        });
    });
}

function initActions() {
    qsa("[data-api-action]").forEach((button) => {
        button.addEventListener("click", async () => {
            const targetId = button.dataset.targetFeedback;
            const feedbackNode = targetId ? document.getElementById(targetId) : null;
            try {
                const method = (button.dataset.apiMethod || "PATCH").toLowerCase();
                const path = button.dataset.apiPath;
                if (method === "post") await api.post(path, {});
                else await api.patch(path, {});
                if (feedbackNode) show(feedbackNode, true, feedbackNode.textContent || "Успешно");
            } catch (actionError) {
                if (feedbackNode) show(feedbackNode, true, actionError.message || "Ошибка");
            }
        });
    });
}

function initSearchSuggestions() {
    qsa("[data-search-input]").forEach((input) => {
        const box = qs("[data-search-suggestions]", input.closest("[data-search-shell]") || input.parentElement);
        if (!box) return;
        input.addEventListener("input", async () => {
            const q = input.value.trim();
            if (q.length < 2) {
                box.classList.add("d-none");
                box.innerHTML = "";
                return;
            }
            try {
                const payload = await api.search.suggestions({ q, limit: 5 });
                const items = payload?.data || [];
                box.innerHTML = items.map((item) => `<a class="dropdown-item py-2" href="${escapeHtml(item.url || "#")}">${escapeHtml(item.label || item.title || item.slug || q)}</a>`).join("");
                box.classList.toggle("d-none", items.length === 0);
                box.classList.toggle("show", items.length > 0);
            } catch (_error) {
                box.classList.add("d-none");
                box.classList.remove("show");
            }
        });
    });
}

function initTicker() {
    const node = qs("[data-live-ticker]");
    if (!node) return;
    const labels = [
        "Live feed synced",
        "Court updates incoming",
        "Point-by-point ready",
        "Scoreboard online",
    ];
    let index = 0;
    window.setInterval(() => {
        setText(node, labels[index % labels.length]);
        index += 1;
    }, 2800);
}

export function showToast(message, type = "primary") {
    const container = document.getElementById("toast-container");
    if (!container || !window.bootstrap?.Toast) return;
    const wrapper = document.createElement("div");
    wrapper.className = `toast align-items-center border-0 text-bg-${type}`;
    wrapper.setAttribute("role", "status");
    wrapper.innerHTML = `<div class="d-flex"><div class="toast-body">${escapeHtml(message)}</div><button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Закрыть"></button></div>`;
    container.appendChild(wrapper);
    const toast = new window.bootstrap.Toast(wrapper, { delay: 2600 });
    wrapper.addEventListener("hidden.bs.toast", () => wrapper.remove());
    toast.show();
}

export function initGlobalUI() {
    initActiveNav();
    activateTabs();
    initForms();
    initActions();
    initSearchSuggestions();
    initTicker();
}
