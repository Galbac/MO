import { escapeHtml, setHtml, show } from "/static/js/core/utils.js";

export function renderSkeletonCards(targetId, count = 3) {
    setHtml(
        targetId,
        Array.from({ length: count }, () => '<div class="entity-card"><div class="skeleton card"></div></div>').join(""),
    );
}

export function renderSkeletonTemplate(targetId, markup) {
    setHtml(targetId, markup);
}

export function renderState({ targetId, emptyId, errorId, error, items, renderer, emptyText = "Нет данных" }) {
    if (error) {
        show(errorId, true, error.message || String(error));
        if (emptyId) show(emptyId, false);
        setHtml(targetId, "");
        return;
    }

    show(errorId, false);
    const list = items || [];
    if (list.length === 0) {
        if (emptyId) show(emptyId, true, emptyText);
        setHtml(targetId, "");
        return;
    }

    if (emptyId) show(emptyId, false);
    setHtml(targetId, list.map(renderer).join(""));
}

export function inlineEmpty(text) {
    return `<div class="state-card"><div class="empty-icon">○</div><strong>${escapeHtml(text)}</strong></div>`;
}

export function inlineError(text) {
    return `<div class="state-card"><div class="error-icon">!</div><strong>${escapeHtml(text)}</strong></div>`;
}
