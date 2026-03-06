let lastToken = null;

async function checkReloadToken() {
    try {
        const response = await fetch("/__dev__/reload-token", {
            cache: "no-store",
            headers: { Accept: "application/json" },
        });
        if (!response.ok) return;
        const payload = await response.json();
        if (!payload?.enabled) return;
        if (lastToken === null) {
            lastToken = payload.token;
            return;
        }
        if (payload.token !== lastToken) {
            window.location.reload();
        }
    } catch (_error) {
        // Ignore temporary network issues during container restarts.
    }
}

window.setInterval(checkReloadToken, 1000);
checkReloadToken();
