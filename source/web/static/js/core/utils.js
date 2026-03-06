export function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}

export function qs(selector, root = document) {
    return root.querySelector(selector);
}

export function qsa(selector, root = document) {
    return [...root.querySelectorAll(selector)];
}

export function setHtml(target, html) {
    const node = typeof target === "string" ? document.getElementById(target) : target;
    if (node) node.innerHTML = html;
}

export function setText(target, value) {
    const node = typeof target === "string" ? document.getElementById(target) : target;
    if (node) node.textContent = String(value ?? "");
}

export function show(nodeOrId, visible = true, text = null) {
    const node = typeof nodeOrId === "string" ? document.getElementById(nodeOrId) : nodeOrId;
    if (!node) return;
    node.classList.toggle("d-none", !visible);
    if (text !== null) node.textContent = text;
}

export function extractList(payload) {
    if (!payload) return [];
    if (Array.isArray(payload.data)) return payload.data;
    if (Array.isArray(payload.items)) return payload.items;
    return [];
}

export function extractData(payload, fallback = {}) {
    if (!payload) return fallback;
    if (payload.data && !Array.isArray(payload.data)) return payload.data;
    return payload;
}

export function debounce(fn, wait = 250) {
    let timer = null;
    return (...args) => {
        clearTimeout(timer);
        timer = window.setTimeout(() => fn(...args), wait);
    };
}

export function initials(name = "") {
    return String(name)
        .split(" ")
        .filter(Boolean)
        .slice(0, 2)
        .map((item) => item[0])
        .join("")
        .toUpperCase();
}

export function formatDate(value, options = {}) {
    if (!value) return "TBD";
    try {
        return new Intl.DateTimeFormat("ru-RU", {
            day: "2-digit",
            month: "short",
            hour: "2-digit",
            minute: "2-digit",
            ...options,
        }).format(new Date(value));
    } catch (_error) {
        return String(value);
    }
}

export function statusLabel(value) {
    return String(value ?? "")
        .replaceAll("_", " ")
        .replace(/\b\w/g, (char) => char.toUpperCase());
}

export function slugFromPath() {
    return window.location.pathname.split("/").filter(Boolean).at(-1) || "";
}

export function entityId() {
    return document.body.dataset.entityId || "";
}

export function pageName() {
    return document.body.dataset.page || "";
}

export function isPublicPage() {
    return document.body.dataset.section === "public";
}

export function isAdminPage() {
    return document.body.dataset.section === "admin";
}

export function toQuery(params = {}) {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
        if (value === undefined || value === null || value === "") return;
        query.set(key, String(value));
    });
    const serialized = query.toString();
    return serialized ? `?${serialized}` : "";
}

export function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
}

export function queryParam(name) {
    return new URLSearchParams(window.location.search).get(name) || "";
}
