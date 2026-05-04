const API_URL = "https://knowledge-system-production.up.railway.app";
const EXTENSION_API_KEY = "080f32884e698da3e2ef2600670fe0e210be93314bdf958d89af0142f9480004";

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!message || message.type !== "xylem:ask") return;

  (async () => {
    try {
      const res = await fetch(`${API_URL}/api/oracle/ask`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Extension-Key": EXTENSION_API_KEY,
        },
        body: JSON.stringify({
          question: message.payload?.question || "",
          user_email: message.payload?.userEmail || "extension@local",
          session_id: message.payload?.sessionId || "",
        }),
      });

      if (!res.ok) {
        const bodyText = await res.text().catch(() => "");
        sendResponse({ ok: false, error: `API request failed (${res.status}) ${bodyText}` });
        return;
      }

      const data = await res.json();
      sendResponse({ ok: true, data });
    } catch (e) {
      sendResponse({ ok: false, error: e?.message || "Network failure" });
    }
  })();

  return true;
});
