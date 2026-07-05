(() => {
  if (window.__foxiWidgetLoaded) return;
  window.__foxiWidgetLoaded = true;

  const script = document.currentScript || Array.from(document.scripts).find((node) => {
    return typeof node.src === "string" && node.src.includes("/widget/foxi.js");
  });
  const baseUrl = script && script.src ? new URL(script.src).origin : window.location.origin;
  const apiUrl = `${baseUrl}/api/chat`;
  const storageKey = "foxinburg.webchat.session_id";
  const greeting = "Привет! Я Фокси из Фоксинбурга 🦊\n\nМогу помочь с курсами, ценами, филиалами и домашкой.";

  let sessionId = "";
  try {
    sessionId = window.localStorage.getItem(storageKey) || "";
  } catch (_) {
    sessionId = "";
  }

  const state = {
    open: false,
    greeted: false,
    messages: [],
  };

  const style = document.createElement("style");
  style.textContent = `
    .fxb-foxi-root{position:fixed;right:20px;bottom:20px;z-index:2147483647;font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
    .fxb-foxi-toggle{width:60px;height:60px;border-radius:999px;border:none;background:linear-gradient(180deg,#7c3aed,#5b21b6);color:#fff;box-shadow:0 16px 36px rgba(91,33,182,.34);font-size:28px;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:transform .2s ease,box-shadow .2s ease}
    .fxb-foxi-toggle:hover{transform:translateY(-2px);box-shadow:0 18px 42px rgba(91,33,182,.42)}
    .fxb-foxi-panel{position:absolute;right:0;bottom:78px;width:360px;max-width:calc(100vw - 24px);height:540px;max-height:calc(100vh - 120px);background:#fff;border-radius:24px;box-shadow:0 24px 80px rgba(15,23,42,.28);display:none;overflow:hidden;border:1px solid rgba(148,163,184,.22);flex-direction:column}
    .fxb-foxi-panel.open{display:flex}
    .fxb-foxi-head{padding:16px 18px;background:linear-gradient(180deg,#6d28d9,#4c1d95);color:#fff}
    .fxb-foxi-brand{display:flex;align-items:center;gap:10px;font-weight:700;font-size:16px}
    .fxb-foxi-brand .avatar{width:36px;height:36px;border-radius:50%;background:rgba(255,255,255,.14);display:flex;align-items:center;justify-content:center;font-size:20px}
    .fxb-foxi-sub{font-size:12px;opacity:.9;margin-top:4px}
    .fxb-foxi-close{position:absolute;right:12px;top:12px;background:rgba(255,255,255,.12);border:none;color:#fff;width:34px;height:34px;border-radius:999px;cursor:pointer;font-size:20px;line-height:1}
    .fxb-foxi-messages{flex:1;overflow:auto;padding:16px;background:linear-gradient(180deg,#f8fafc,#fff);display:flex;flex-direction:column;gap:12px}
    .fxb-foxi-row{display:flex}
    .fxb-foxi-row.user{justify-content:flex-end}
    .fxb-foxi-row.bot{justify-content:flex-start}
    .fxb-foxi-bubble{max-width:82%;border-radius:18px;padding:12px 14px;white-space:pre-wrap;line-height:1.45;font-size:14px;box-shadow:0 8px 22px rgba(15,23,42,.06)}
    .fxb-foxi-bubble.user{background:#6d28d9;color:#fff;border-bottom-right-radius:6px}
    .fxb-foxi-bubble.bot{background:#fff;color:#0f172a;border:1px solid rgba(148,163,184,.18);border-bottom-left-radius:6px}
    .fxb-foxi-buttons{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
    .fxb-foxi-link{display:inline-flex;align-items:center;justify-content:center;padding:9px 12px;border-radius:999px;background:#f3e8ff;color:#5b21b6;text-decoration:none;font-size:13px;font-weight:600}
    .fxb-foxi-link:hover{background:#e9d5ff}
    .fxb-foxi-composer{display:flex;gap:8px;padding:12px;border-top:1px solid rgba(148,163,184,.18);background:#fff}
    .fxb-foxi-input{flex:1;min-height:44px;max-height:120px;resize:none;border:1px solid #dbe4f0;border-radius:16px;padding:12px 14px;font:inherit;outline:none}
    .fxb-foxi-input:focus{border-color:#8b5cf6;box-shadow:0 0 0 3px rgba(139,92,246,.12)}
    .fxb-foxi-send{min-width:76px;border:none;border-radius:16px;background:#6d28d9;color:#fff;font-weight:700;cursor:pointer;padding:0 14px}
    .fxb-foxi-send:disabled{opacity:.6;cursor:not-allowed}
    .fxb-foxi-typing{font-size:12px;color:#64748b;padding:0 16px 10px}
    @media (max-width: 640px){
      .fxb-foxi-root{right:12px;bottom:12px}
      .fxb-foxi-panel{right:0;bottom:74px;width:calc(100vw - 24px);height:min(72vh,620px)}
    }
  `;
  document.head.appendChild(style);

  const root = document.createElement("div");
  root.className = "fxb-foxi-root";

  const panel = document.createElement("div");
  panel.className = "fxb-foxi-panel";

  const head = document.createElement("div");
  head.className = "fxb-foxi-head";
  head.innerHTML = `
    <button type="button" class="fxb-foxi-close" aria-label="Закрыть чат">×</button>
    <div class="fxb-foxi-brand">
      <div class="avatar">🦊</div>
      <div>
        <div>Фокси • Фоксинбург</div>
        <div class="fxb-foxi-sub">Онлайн-помощник по курсам и домашке</div>
      </div>
    </div>
  `;

  const messages = document.createElement("div");
  messages.className = "fxb-foxi-messages";

  const typing = document.createElement("div");
  typing.className = "fxb-foxi-typing";
  typing.hidden = true;
  typing.textContent = "Фокси печатает…";

  const composer = document.createElement("form");
  composer.className = "fxb-foxi-composer";
  composer.innerHTML = `
    <textarea class="fxb-foxi-input" rows="1" placeholder="Напишите сообщение…"></textarea>
    <button type="submit" class="fxb-foxi-send">Отправить</button>
  `;

  const toggle = document.createElement("button");
  toggle.className = "fxb-foxi-toggle";
  toggle.type = "button";
  toggle.setAttribute("aria-label", "Открыть чат");
  toggle.setAttribute("aria-expanded", "false");
  toggle.textContent = "🦊";

  panel.appendChild(head);
  panel.appendChild(messages);
  panel.appendChild(typing);
  panel.appendChild(composer);
  root.appendChild(panel);
  root.appendChild(toggle);
  const mountTarget = document.body || document.documentElement;
  mountTarget.appendChild(root);

  const closeBtn = head.querySelector(".fxb-foxi-close");
  const input = composer.querySelector(".fxb-foxi-input");
  const sendBtn = composer.querySelector(".fxb-foxi-send");

  function persistSession(id) {
    sessionId = id || sessionId;
    try {
      if (sessionId) window.localStorage.setItem(storageKey, sessionId);
    } catch (_) {
      /* ignore */
    }
  }

  function scrollToBottom() {
    messages.scrollTop = messages.scrollHeight;
  }

  function addMessage(role, text, buttons) {
    const row = document.createElement("div");
    row.className = `fxb-foxi-row ${role}`;
    const bubble = document.createElement("div");
    bubble.className = `fxb-foxi-bubble ${role}`;
    bubble.textContent = text;
    row.appendChild(bubble);
    if (buttons && buttons.length) {
      const buttonsWrap = document.createElement("div");
      buttonsWrap.className = "fxb-foxi-buttons";
      buttons.forEach((button) => {
        if (!button || !button.url) return;
        const a = document.createElement("a");
        a.className = "fxb-foxi-link";
        a.href = button.url;
        a.target = "_blank";
        a.rel = "noopener noreferrer";
        a.textContent = button.title || button.url || "Открыть";
        buttonsWrap.appendChild(a);
      });
      if (buttonsWrap.childNodes.length) bubble.appendChild(buttonsWrap);
    }
    messages.appendChild(row);
    scrollToBottom();
  }

  function ensureGreeting() {
    if (state.greeted || state.messages.length > 0) return;
    state.greeted = true;
    addMessage("bot", greeting);
  }

  function setOpen(nextOpen) {
    state.open = nextOpen;
    panel.classList.toggle("open", nextOpen);
    toggle.setAttribute("aria-expanded", String(nextOpen));
    if (nextOpen) {
      ensureGreeting();
      setTimeout(() => input.focus(), 0);
    }
  }

  async function submitMessage(text) {
    const cleanText = text.trim();
    if (!cleanText) return;

    state.messages.push({ role: "user", text: cleanText });
    addMessage("user", cleanText);
    input.value = "";
    sendBtn.disabled = true;
    typing.hidden = false;

    try {
      const response = await fetch(apiUrl, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          session_id: sessionId || undefined,
          text: cleanText,
        }),
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = await response.json();
      persistSession(data.session_id);
      const reply = typeof data.reply === "string" ? data.reply : "Извините, не удалось получить ответ.";
      const buttons = Array.isArray(data.buttons) ? data.buttons : [];
      state.messages.push({ role: "bot", text: reply });
      addMessage("bot", reply, buttons);
    } catch (error) {
      addMessage("bot", "Не получилось отправить сообщение. Попробуйте ещё раз чуть позже 🙏");
    } finally {
      typing.hidden = true;
      sendBtn.disabled = false;
      input.focus();
    }
  }

  toggle.addEventListener("click", () => setOpen(!state.open));
  closeBtn.addEventListener("click", () => setOpen(false));

  composer.addEventListener("submit", (event) => {
    event.preventDefault();
    submitMessage(input.value);
  });

  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submitMessage(input.value);
    }
  });
})();
