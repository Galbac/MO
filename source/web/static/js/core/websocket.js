const FALLBACK_PATH = document.body.dataset.liveWsPath || "/api/v1/live/ws/live";

export function createLiveSocket(channels = [], onMessage = () => {}, { path = FALLBACK_PATH } = {}) {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const query = channels.length ? `?channels=${encodeURIComponent(channels.join(","))}` : "";
    const socket = new WebSocket(`${protocol}//${window.location.host}${path}${query}`);

    socket.addEventListener("message", (event) => {
        try {
            const payload = JSON.parse(event.data);
            if (payload.event === "connected" || payload.event === "subscribed") return;
            onMessage(payload);
        } catch (_error) {
            onMessage(event.data);
        }
    });

    return socket;
}
