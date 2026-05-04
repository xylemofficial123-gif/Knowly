(() => {
  if (document.getElementById("xylem-launcher")) return;

  const state = {
    sessionId: "",
    userEmail: "extension@local",
    loading: false,
    closed: false,
  };

  const launcher = document.createElement("button");
  launcher.id = "xylem-launcher";
  launcher.textContent = "✦";
  launcher.title = "Open Xylem Chat";

  const reopen = document.createElement("button");
  reopen.id = "xylem-reopen";
  reopen.textContent = "Open Xylem";
  reopen.title = "Reopen Xylem Chat";
  reopen.style.display = "none";

  const panel = document.createElement("div");
  panel.id = "xylem-panel";
  panel.style.display = "none";

  panel.innerHTML = `
    <div class="x-header">
      <span class="x-title">Xylem Chat</span>
      <div class="x-header-actions">
        <button id="x-min" class="x-min-btn">Minimize</button>
        <button id="x-close" class="x-close-btn" aria-label="Close">×</button>
      </div>
    </div>
    <div id="x-messages" class="x-messages"></div>
    <div class="x-input-wrap">
      <textarea id="x-q" placeholder="Ask..." rows="1"></textarea>
      <button id="x-send" aria-label="Send">➔</button>
    </div>
  `;

  document.body.appendChild(launcher);
  document.body.appendChild(reopen);
  document.body.appendChild(panel);

  const messagesEl = panel.querySelector("#x-messages");
  const qEl = panel.querySelector("#x-q");
  const sendEl = panel.querySelector("#x-send");
  const minEl = panel.querySelector("#x-min");
  const closeEl = panel.querySelector("#x-close");

  function setOpen(open) {
    if (state.closed) return;
    panel.style.display = open ? "flex" : "none";
    launcher.style.display = open ? "none" : "block";
    reopen.style.display = "none";
    if (open) qEl.focus();
  }

  function closeWidget() {
    state.closed = true;
    panel.style.display = "none";
    launcher.style.display = "none";
    reopen.style.display = "block";
  }

  function reopenWidget() {
    state.closed = false;
    reopen.style.display = "none";
    launcher.style.display = "block";
    setOpen(true);
  }

  function shortAnswer(text = "") {
    const clean = String(text).trim();
    if (!clean) return "No response.";

    const parts = clean.match(/[^.!?]+[.!?]?/g) || [];
    const sentences = parts.map((s) => s.trim()).filter(Boolean);

    if (sentences.length > 1) {
      const compact = sentences.slice(0, 2).join(" ");
      return compact.length > 260 ? `${compact.slice(0, 257)}...` : compact;
    }

    return clean.length > 220 ? `${clean.slice(0, 217)}...` : clean;
  }

  function appendMsg(role, text) {
    const node = document.createElement("div");
    node.className = `x-msg ${role}`;
    node.textContent = text;
    messagesEl.appendChild(node);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function appendStatus(text) {
    const node = document.createElement("div");
    node.className = "x-status";
    node.textContent = text;
    messagesEl.appendChild(node);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return node;
  }

  async function askOracle(question) {
    return await new Promise((resolve, reject) => {
      chrome.runtime.sendMessage(
        {
          type: "xylem:ask",
          payload: {
            question,
            userEmail: state.userEmail,
            sessionId: state.sessionId,
          },
        },
        (response) => {
          if (chrome.runtime.lastError) {
            reject(new Error(`Extension runtime error: ${chrome.runtime.lastError.message}`));
            return;
          }
          if (!response?.ok) {
            reject(new Error(response?.error || "Request failed"));
            return;
          }
          const data = response.data || {};
          if (data.session_id) state.sessionId = data.session_id;
          resolve(data);
        }
      );
    });
  }

  async function onSend() {
    if (state.loading) return;

    const q = qEl.value.trim();
    if (!q) return;

    qEl.value = "";
    appendMsg("user", q);
    state.loading = true;
    sendEl.disabled = true;

    const statusNode = appendStatus("Thinking...");

    try {
      const data = await askOracle(q);
      statusNode.remove();
      appendMsg("assistant", shortAnswer(data.answer || ""));
    } catch (err) {
      statusNode.remove();
      appendMsg("assistant", `Error: ${err?.message || "Failed to fetch answer"}`);
    } finally {
      state.loading = false;
      sendEl.disabled = false;
      qEl.focus();
    }
  }

  launcher.addEventListener("click", () => setOpen(true));
  reopen.addEventListener("click", reopenWidget);
  minEl.addEventListener("click", () => setOpen(false));
  closeEl.addEventListener("click", closeWidget);
  sendEl.addEventListener("click", onSend);

  qEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  });
})();
