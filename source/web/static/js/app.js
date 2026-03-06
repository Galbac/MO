import { initAuth } from "/static/js/core/auth.js";
import { initGlobalUI } from "/static/js/core/ui.js";
import { initNotificationsUI } from "/static/js/core/notifications.js";
import { initPublicPages } from "/static/js/pages/public.js";
import { initAdminPages } from "/static/js/pages/admin.js";

document.addEventListener("DOMContentLoaded", async () => {
    initGlobalUI();
    initAuth();
    initNotificationsUI();
    await initPublicPages();
    await initAdminPages();
});
