/* Фоксинбург CRM: inbox, карточки клиентов, дашборд, рассылки, вопросы.
 *
 * Токен живёт только в localStorage этого браузера и уходит исключительно
 * заголовком X-Admin-Token — в URL его класть нельзя, он осядет в логах
 * прокси и в истории браузера.
 */
const TOKEN_KEY = "foxinburg-admin-token";
const SESSION_KEY = "foxinburg-admin-session";
const REQUEST_TIMEOUT_MS = 20000;
const POLL_MS = 5000;

// Сессия RBAC: {token, role, username, permissions}. Старый ключ с голым
// токеном (super_admin) поддерживаем для обратной совместимости.
let SESSION = null;
try {
  SESSION = JSON.parse(localStorage.getItem(SESSION_KEY) || "null");
} catch (_) {
  SESSION = null;
}
let TOKEN = (SESSION && SESSION.token) || localStorage.getItem(TOKEN_KEY) || "";
let PERMISSIONS = (SESSION && SESSION.permissions) || [];
let SECTION = "dashboard";

function hasPerm(perm) {
  return PERMISSIONS.includes("*") || PERMISSIONS.includes(perm);
}

const $ = (id) => document.getElementById(id);

function esc(value) {
  return String(value == null ? "" : value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

async function api(path, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const resp = await fetch(path, {
      ...options,
      signal: controller.signal,
      headers: {
        "X-Admin-Token": TOKEN,
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...(options.headers || {}),
      },
    });
    if (resp.status === 401) throw new Error("unauthorized");
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({}));
      throw new Error(body.detail || `Сервер ответил ${resp.status}`);
    }
    return await resp.json();
  } catch (err) {
    if (err.name === "AbortError") throw new Error("Сервер не ответил вовремя");
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

function toast(message) {
  const el = $("toast");
  el.textContent = message;
  el.hidden = false;
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => { el.hidden = true; }, 3200);
}

function fmtTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d)) return String(iso).slice(0, 16).replace("T", " ");
  const today = new Date();
  const sameDay = d.toDateString() === today.toDateString();
  const hm = d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
  return sameDay ? hm : `${d.toLocaleDateString("ru-RU")} ${hm}`;
}

const CHANNEL_LABEL = { max: "MAX", telegram: "Telegram", web: "Веб" };
const LEAD_LABELS = {
  new: "Новый", contacted: "Контакт", qualified: "Квалифицирован",
  trial: "Пробный", offer: "Предложение", payment: "Оплата",
  client: "Клиент", lost: "Потерян", none: "—",
};
const AI_LABELS = { active: "AI активен", paused: "AI на паузе", manager: "Менеджер" };

function channelPill(channel) {
  return `<span class="pill pill--${esc(channel)}">${esc(CHANNEL_LABEL[channel] || channel)}</span>`;
}

function aiPill(mode) {
  if (mode === "active") return `<span class="pill pill--ai">AI</span>`;
  return `<span class="pill pill--${esc(mode)}">${esc(AI_LABELS[mode] || mode)}</span>`;
}

function initials(name, fallback) {
  const parts = String(name || "").trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return (fallback || "?").slice(0, 2).toUpperCase();
  return parts.slice(0, 2).map((p) => p[0].toUpperCase()).join("");
}

/* --- вход ----------------------------------------------------------------- */

function showGate(message) {
  $("gate").hidden = false;
  $("app").hidden = true;
  const error = $("gate-error");
  error.hidden = !message;
  error.textContent = message || "";
}

async function enter(value) {
  TOKEN = value;
  const me = await api("/admin/api/me"); // заодно проверка токена
  PERMISSIONS = me.permissions || [];
  SESSION = { token: value, role: me.role, username: me.username, permissions: PERMISSIONS };
  localStorage.setItem(SESSION_KEY, JSON.stringify(SESSION));
  localStorage.setItem(TOKEN_KEY, value);
  applyPermissions();
  $("gate").hidden = true;
  $("app").hidden = false;
  if (location.hash.replace(/^#\/?/, "")) {
    routeFromHash();
  } else {
    showSection(hasPerm("stats") ? "dashboard" : "inbox");
  }
  startPolling();
}

async function login(username, password) {
  const resp = await fetch("/admin/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (resp.status === 401) throw new Error("Неверный логин или пароль");
  if (resp.status === 429) throw new Error("Слишком много попыток — подождите минуту");
  if (!resp.ok) throw new Error("Сервер ответил " + resp.status);
  const data = await resp.json();
  await enter(data.token);
}

function applyPermissions() {
  document.querySelectorAll(".nav-item[data-perm]").forEach((el) => {
    el.hidden = !hasPerm(el.dataset.perm);
  });
  const user = SESSION ? `${SESSION.username} · ${SESSION.role}` : "";
  $("topbar-user").textContent = user;
}

$("gate-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const username = $("gate-username").value.trim();
  const password = $("gate-password").value;
  if (!username || !password) return;
  try {
    await login(username, password);
  } catch (err) {
    showGate(err.message);
  }
});

$("gate-token-toggle").addEventListener("click", () => {
  $("gate-token-form").hidden = !$("gate-token-form").hidden;
});

$("gate-token-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const value = $("gate-token").value.trim();
  if (!value) return;
  try {
    await enter(value);
  } catch (err) {
    showGate(err.message === "unauthorized" ? "Токен не подошёл" : err.message);
  }
});

$("logout").addEventListener("click", () => {
  api("/admin/api/logout", { method: "POST", body: "{}" }).catch(() => {});
  localStorage.removeItem(SESSION_KEY);
  localStorage.removeItem(TOKEN_KEY);
  TOKEN = "";
  SESSION = null;
  PERMISSIONS = [];
  $("gate-password").value = "";
  $("gate-token").value = "";
  stopPolling();
  showGate("");
});

$("burger").addEventListener("click", () => {
  document.querySelector(".sidebar").classList.toggle("sidebar--open");
});

/* --- навигация ------------------------------------------------------------ */

function showSection(name, options = {}) {
  document.querySelectorAll(".nav-item[data-section]").forEach((el) =>
    el.classList.toggle("nav-item--active", el.dataset.section === name));
  const sectionPerms = {
    dashboard: "stats", inbox: "inbox", requests: "inbox", customers: "customers",
    pipeline: "pipeline", broadcast: "broadcasts", insights: "stats",
    analytics: "analytics", kb: "kb", ai: "prompts", errors: "errors",
    users: "users", settings: "system",
  };
  if (!hasPerm(sectionPerms[name] || "stats")) name = "inbox";
  SECTION = name;
  ["dashboard", "inbox", "requests", "customers", "pipeline", "broadcast", "insights",
   "analytics", "kb", "ai", "errors", "users", "settings"].forEach((s) => {
    $(`page-${s}`).hidden = s !== name;
  });
  document.querySelector(".sidebar").classList.remove("sidebar--open");
  if (!options.keepHash) setHash("#/" + name);
  if (name === "dashboard") loadDashboard();
  if (name === "inbox") loadInbox();
  if (name === "requests") loadRequests();
  if (name === "customers") loadCustomers();
  if (name === "pipeline") loadPipeline();
  if (name === "broadcast") loadBroadcastCenter();
  if (name === "analytics") loadAnalytics();
  if (name === "kb") loadKb();
  if (name === "ai") loadAiSection();
  if (name === "errors") loadErrors();
  if (name === "insights") loadInsights();
  if (name === "users") loadAdminUsers();
  if (name === "settings") loadSettings();
}

$("nav").addEventListener("click", (event) => {
  const item = event.target.closest(".nav-item[data-section]");
  if (item) showSection(item.dataset.section);
});

/* --- hash-роутинг (shareable deep links) ----------------------------------- */

/* setHash выставляет location.hash без навигации; свой же hashchange
   подавляем флагом, чтобы не было зацикливания с routeFromHash. */
let HASH_SILENT = false;

function setHash(hash) {
  if (location.hash === hash) return;
  HASH_SILENT = true;
  location.hash = hash;
}

window.addEventListener("hashchange", () => {
  if (HASH_SILENT) {
    HASH_SILENT = false;
    return;
  }
  routeFromHash();
});

function routeFromHash() {
  if ($("app").hidden) return; // до входа в админку роутить нечего
  const parts = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  const section = parts[0];
  const id = Number(parts[1]) || 0;
  if (!section) return;
  if (section === "requests") {
    showSection("requests", { keepHash: true });
    if (id) openRequest(id);
  } else if (section === "inbox") {
    showSection("inbox", { keepHash: true });
    if (id) openConversationById(id);
  } else if (section === "customers") {
    showSection("customers", { keepHash: true });
    if (id) openCustomerById(id);
  } else if (document.querySelector(`.nav-item[data-section="${section}"]`)) {
    showSection(section, { keepHash: true });
  }
}

/* --- поллинт -------------------------------------------------------------- */

let pollTimer = null;

function startPolling() {
  stopPolling();
  pollTimer = setInterval(() => {
    refreshHealth();
    if (SECTION === "inbox") {
      loadInbox({ silent: true });
      if (INBOX.activeId) loadMessages(INBOX.activeId, { silent: true });
    }
    if (SECTION === "requests") loadRequests({ silent: true });
    if (SECTION === "dashboard") loadDashboard({ silent: true });
  }, POLL_MS);
}

function stopPolling() {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = null;
}

/* --- дашборд -------------------------------------------------------------- */

async function refreshHealth() {
  try {
    const h = await api("/admin/api/health");
    $("health-dots").innerHTML = [
      ["БД", h.db_ok], ["MAX", h.max_ok], ["TG", h.telegram_ok],
    ].map(([label, ok]) =>
      `<span class="dot-label">${label}</span><span class="dot ${ok ? "dot--ok" : ""}"></span>`
    ).join("");
  } catch (err) { /* токен протух — обработает основной загрузчик */ }
}

async function loadDashboard() {
  try {
    const [stats, inbox] = await Promise.all([
      api("/admin/api/stats/today"),
      api("/admin/api/inbox?limit=10"),
    ]);
    const cards = [
      [stats.new_customers.today, `Новые клиенты сегодня (7д: ${stats.new_customers.d7}, 30д: ${stats.new_customers.d30})`],
      [stats.active_conversations, "Активные диалоги"],
      [stats.unread_conversations, "Непрочитанные"],
      [`${stats.messages_today.in} / ${stats.messages_today.out}`, "Сообщения in/out сегодня"],
      [stats.ai_events_today.handoff, "Передано менеджеру сегодня"],
      [stats.ai_events_today.no_answer, "Без ответа сегодня"],
    ];
    $("dash-cards").innerHTML = cards.map(([value, label]) =>
      `<div class="card"><div class="card__value">${esc(value)}</div><div class="card__label">${esc(label)}</div></div>`
    ).join("");
    $("dash-channels").innerHTML = (stats.by_channel || []).length
      ? stats.by_channel.map((row) =>
          `<p>${channelPill(row.channel)} <b>${esc(row.c)}</b> сообщений</p>`).join("")
      : `<p class="muted">Сегодня сообщений ещё не было</p>`;
    $("dash-latest").innerHTML = (inbox.items || []).length
      ? inbox.items.map(convRowHtml).join("")
      : `<p class="muted">Обращений пока нет</p>`;
    refreshHealth();
  } catch (err) {
    if (err.message === "unauthorized") showGate("Токен больше не подходит");
    else toast(err.message);
  }
}

/* --- inbox ---------------------------------------------------------------- */

const INBOX = { items: [], activeId: 0, active: null, oldestMessageId: 0 };

function inboxQuery() {
  const params = new URLSearchParams();
  if ($("inbox-channel").value) params.set("channel", $("inbox-channel").value);
  if ($("inbox-ai").value) params.set("ai_mode", $("inbox-ai").value);
  if ($("inbox-lead").value) params.set("lead_status", $("inbox-lead").value);
  if ($("inbox-unread").checked) params.set("unread", "true");
  if ($("inbox-from").value) params.set("date_from", $("inbox-from").value);
  if ($("inbox-to").value) params.set("date_to", $("inbox-to").value + "T23:59:59");
  if ($("inbox-search").value.trim()) params.set("search", $("inbox-search").value.trim());
  params.set("limit", "100");
  return params.toString();
}

function convRowHtml(item) {
  const name = item.customer_name || item.customer_phone || item.external_user_id;
  const tags = (item.tags || []).map((t) => `<span class="pill pill--tag">${esc(t.name)}</span>`).join("");
  return `
    <button class="conv ${item.id === INBOX.activeId ? "conv--active" : ""}" data-conv="${item.id}">
      <span class="avatar avatar--${esc(item.channel)}">${esc(initials(item.customer_name, CHANNEL_LABEL[item.channel]))}</span>
      <span class="conv__body">
        <span class="conv__top">
          <span class="conv__name">${esc(name)}</span>
          <span class="conv__time">${esc(fmtTime(item.last_message_at))}</span>
        </span>
        <span class="conv__last">${esc(item.last_message_text || "")}</span>
        <span class="conv__meta">
          ${channelPill(item.channel)} ${aiPill(item.ai_mode)}
          ${item.manager ? `<span class="pill pill--mgr" title="Кто ведёт диалог">Ведёт: ${esc(item.manager)}</span>` : ""}
          ${item.lead_status && item.lead_status !== "none" ? `<span class="pill pill--lead">${esc(LEAD_LABELS[item.lead_status] || item.lead_status)}</span>` : ""}
          ${tags}
          ${item.unread_count ? `<span class="unread-badge">${item.unread_count}</span>` : ""}
        </span>
      </span>
    </button>`;
}

async function loadInbox(options = {}) {
  try {
    const data = await api(`/admin/api/inbox?${inboxQuery()}`);
    INBOX.items = data.items || [];
    const unread = INBOX.items.reduce((sum, item) => sum + (item.unread_count ? 1 : 0), 0);
    $("nav-unread").hidden = !unread;
    $("nav-unread").textContent = unread || "";
    $("inbox-items").innerHTML = INBOX.items.length
      ? INBOX.items.map(convRowHtml).join("")
      : `<div class="empty">Диалогов нет</div>`;
  } catch (err) {
    if (!options.silent) {
      if (err.message === "unauthorized") showGate("Токен больше не подходит");
      else toast(err.message);
    }
  }
}

["inbox-channel", "inbox-ai", "inbox-lead", "inbox-unread", "inbox-from", "inbox-to"]
  .forEach((id) => $(id).addEventListener("change", () => loadInbox()));
$("inbox-search").addEventListener("input", () => loadInbox());

$("inbox-items").addEventListener("click", (event) => openConversation(event));
$("dash-latest").addEventListener("click", (event) => {
  showSection("inbox");
  openConversation(event);
});

async function openConversation(event) {
  const row = event.target.closest("[data-conv]");
  if (!row) return;
  await openConversationById(Number(row.dataset.conv));
}

/* Адаптер для deep links и глобального поиска: открывает диалог по id,
   даже если он не попал в текущую выдачу фильтров (фильтры сбрасываем). */
async function openConversationById(id) {
  if (!id) return;
  if (!INBOX.items.some((item) => item.id === id)) {
    ["inbox-channel", "inbox-ai", "inbox-lead"].forEach((fid) => { $(fid).value = ""; });
    $("inbox-unread").checked = false;
    $("inbox-search").value = "";
    await loadInbox();
  }
  INBOX.activeId = id;
  INBOX.oldestMessageId = 0;
  pendingClientMessageId = null;
  loadInbox({ silent: true });
  document.querySelector(".page--inbox").classList.add("inbox--chat");
  const conv = INBOX.items.find((item) => item.id === id) || null;
  INBOX.active = conv;
  setHash("#/inbox/" + id);
  $("chat-empty").hidden = true;
  $("chat-wrap").hidden = false;
  renderChatHead(conv);
  await Promise.all([
    loadMessages(id),
    loadCustomerCard(conv ? conv.customer_id : 0),
    loadAvailability(id),
    api(`/admin/api/conversations/${id}/read`, { method: "POST" }).catch(() => {}),
  ]);
  loadInbox({ silent: true });
}

/* --- связь с клиентом (доступность канала) --------------------------------- */

async function loadAvailability(convId) {
  const box = $("chat-avail");
  try {
    const av = await api(`/admin/api/conversations/${convId}/availability`);
    if (av.can_send) {
      box.hidden = true;
      box.innerHTML = "";
      return;
    }
    const c = av.contacts || {};
    const contacts = [];
    if (c.phone) {
      contacts.push(`<a href="tel:${esc(c.phone)}">${esc(c.phone)}</a>
        <button class="btn btn--sm btn--ghost" data-copy="${esc(c.phone)}">Скопировать</button>`);
    }
    if (c.email) {
      contacts.push(`<a href="mailto:${esc(c.email)}">${esc(c.email)}</a>
        <button class="btn btn--sm btn--ghost" data-copy="${esc(c.email)}">Скопировать</button>`);
    }
    if (c.telegram_username) {
      const uname = "@" + String(c.telegram_username).replace(/^@/, "");
      contacts.push(`<span>${esc(uname)}</span>
        <button class="btn btn--sm btn--ghost" data-copy="${esc(uname)}">Скопировать</button>`);
    }
    box.innerHTML = `
      <b>Клиент вне окна доставки (${esc(CHANNEL_LABEL[av.channel] || av.channel)}):</b>
      ${esc(av.reason || "сообщение из чата может не дойти")}
      ${contacts.length ? `<div class="chat-avail__contacts">Связаться напрямую: ${contacts.join(" ")}</div>` : ""}`;
    box.hidden = false;
  } catch (err) {
    box.hidden = true;
    box.innerHTML = "";
  }
}

$("chat-back").addEventListener("click", () => {
  document.querySelector(".page--inbox").classList.remove("inbox--chat");
});

function renderChatHead(conv) {
  if (!conv) return;
  const name = conv.customer_name || conv.customer_phone || conv.external_user_id;
  $("chat-title").textContent = name;
  updateAiButton(conv.ai_mode, conv.ai_paused_until);
  const mgr = $("chat-manager");
  if (mgr) {
    // Кто ведёт диалог в режиме менеджера — видно всей команде.
    mgr.hidden = !conv.manager;
    mgr.textContent = conv.manager ? `Ведёт: ${conv.manager}` : "";
  }
}

function updateAiButton(mode, pausedUntil) {
  const btn = $("ai-toggle");
  btn.textContent = AI_LABELS[mode] || "AI";
  btn.className = "btn btn--sm" + (mode === "active" ? "" : " btn--danger");
  if (mode === "paused" && pausedUntil) {
    btn.textContent = `AI: пауза до ${fmtTime(pausedUntil)}`;
  }
}

/* --- сообщения ------------------------------------------------------------ */

function messageHtml(msg) {
  const baseWho = { customer: "Клиент", ai: "AI", manager: "Менеджер", system: "Система" }[msg.sender_type] || msg.sender_type;
  // У сообщения менеджера показываем, кто именно писал (несколько менеджеров
  // видят все чаты — важно, кто ведёт диалог).
  const who = msg.sender_type === "manager" && msg.sender_name ? msg.sender_name : baseWho;
  const cls = msg.direction === "in" ? "in" : (msg.sender_type === "manager" ? "manager" : "out");
  let statusLine = "";
  if (msg.direction === "out") {
    if (msg.status === "failed") {
      statusLine = `<div class="bubble__status bubble__status--failed" title="${esc(msg.error || "Ошибка доставки")}">
        ✖ не доставлено${msg.error ? `: ${esc(msg.error)}` : ""}
        <button class="btn btn--sm btn--ghost" data-msg-retry="${msg.id}">Повторить</button></div>`;
    } else if (msg.status === "pending") {
      statusLine = `<div class="bubble__status">⏳ ожидает доставки</div>`;
    } else {
      statusLine = `<div class="bubble__status">✓</div>`;
    }
  }
  return `<div class="bubble bubble--${cls}" data-mid="${msg.id}">
    <div class="bubble__meta"><b>${esc(who)}</b><span>${esc(fmtTime(msg.created_at))}</span></div>
    ${esc(msg.text)}${statusLine}</div>`;
}

async function loadMessages(convId, options = {}) {
  try {
    const data = await api(`/admin/api/conversations/${convId}/messages?limit=50`);
    renderMessages(data.items || [], data.has_more);
  } catch (err) {
    if (!options.silent) toast(err.message);
  }
}

function renderMessages(items, hasMore, prepend = false) {
  const box = $("chat-messages");
  const nearBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 120;
  const more = $("chat-more");
  if (prepend) {
    const prevHeight = box.scrollHeight;
    more.insertAdjacentHTML("afterend", items.map(messageHtml).join(""));
    box.scrollTop = box.scrollHeight - prevHeight;
  } else {
    box.querySelectorAll(".bubble").forEach((el) => el.remove());
    more.insertAdjacentHTML("afterend", items.map(messageHtml).join(""));
    if (nearBottom || !renderMessages._touched) box.scrollTop = box.scrollHeight;
  }
  renderMessages._touched = true;
  more.hidden = !hasMore;
  if (items.length) INBOX.oldestMessageId = items[0].id;
}

$("chat-more").addEventListener("click", async () => {
  if (!INBOX.activeId || !INBOX.oldestMessageId) return;
  const data = await api(
    `/admin/api/conversations/${INBOX.activeId}/messages?before_id=${INBOX.oldestMessageId}&limit=50`);
  renderMessages(data.items || [], data.has_more, true);
});

$("chat-messages").addEventListener("scroll", () => { renderMessages._touched = true; });

/* Повторная отправка недоставленного сообщения. */
$("chat-messages").addEventListener("click", async (event) => {
  const retry = event.target.closest("[data-msg-retry]");
  if (!retry) return;
  retry.disabled = true;
  try {
    const result = await api(`/admin/api/messages/${retry.dataset.msgRetry}/retry`,
      { method: "POST", body: "{}" });
    if (result.ok) {
      toast("Сообщение отправлено повторно");
    } else {
      toast(`Снова не доставлено: ${result.error || "ошибка отправки"}`);
    }
  } catch (err) {
    toast(err.message);
  }
  if (INBOX.activeId) loadMessages(INBOX.activeId, { silent: true });
});

/* --- ответ менеджера ------------------------------------------------------ */

/* client_message_id генерируется один раз на черновик: при повторном клике
   или сбое сети тот же идентификатор не даст backend'у отправить дубль. */
let pendingClientMessageId = null;

function newClientMessageId() {
  if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
  return "cmid-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 12);
}

$("chat-text").addEventListener("input", () => {
  if (!pendingClientMessageId && $("chat-text").value.trim()) {
    pendingClientMessageId = newClientMessageId();
  }
});

$("chat-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = $("chat-text").value.trim();
  if (!text || !INBOX.activeId) return;
  if (!pendingClientMessageId) pendingClientMessageId = newClientMessageId();
  const clientMessageId = pendingClientMessageId;
  const submitBtn = $("chat-form").querySelector("button[type=submit]");
  submitBtn.disabled = true;
  submitBtn.textContent = "Отправка…";
  try {
    const result = await api(`/admin/api/conversations/${INBOX.activeId}/reply`, {
      method: "POST",
      body: JSON.stringify({ text, client_message_id: clientMessageId }),
    });
    if (!result.ok || result.status === "failed") {
      toast(`Не доставлено: ${result.error || "ошибка отправки"}`);
    } else {
      // Сообщение принято в отправку — черновик закрыт, следующее сообщение
      // получит новый client_message_id.
      pendingClientMessageId = null;
      $("chat-text").value = "";
    }
    if (INBOX.active && INBOX.active.ai_mode !== "paused") {
      INBOX.active.ai_mode = "manager";
      updateAiButton("manager");
    }
    await loadMessages(INBOX.activeId, { silent: true });
  } catch (err) {
    toast(err.message);
    // Текст и client_message_id сохраняем: повторная отправка идемпотентна.
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Отправить";
  }
});

$("chat-text").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    $("chat-form").requestSubmit();
  }
});

/* --- AI-режим ------------------------------------------------------------- */

$("ai-toggle").addEventListener("click", () => { $("ai-drop").hidden = !$("ai-drop").hidden; });
document.addEventListener("click", (event) => {
  if (!event.target.closest(".ai-menu")) $("ai-drop").hidden = true;
});

$("ai-drop").addEventListener("click", async (event) => {
  const btn = event.target.closest("[data-ai]");
  if (!btn || !INBOX.activeId) return;
  $("ai-drop").hidden = true;
  const mode = btn.dataset.ai;
  let pausedUntil = null;
  if (mode === "paused") {
    const span = btn.dataset.until;
    const now = new Date();
    if (span === "30m") pausedUntil = new Date(now.getTime() + 30 * 60000);
    else if (span === "1h") pausedUntil = new Date(now.getTime() + 60 * 60000);
    else if (span === "3h") pausedUntil = new Date(now.getTime() + 180 * 60000);
    else if (span === "eod") {
      pausedUntil = new Date(now);
      pausedUntil.setHours(23, 59, 59, 0);
    } // пустой span — пауза до ручного включения (null)
  }
  try {
    await api(`/admin/api/conversations/${INBOX.activeId}/ai`, {
      method: "POST",
      body: JSON.stringify({ mode, paused_until: pausedUntil ? pausedUntil.toISOString() : null }),
    });
    if (INBOX.active) INBOX.active.ai_mode = mode;
    updateAiButton(mode, pausedUntil ? pausedUntil.toISOString() : "");
    toast("Режим AI обновлён");
    loadInbox({ silent: true });
  } catch (err) {
    toast(err.message);
  }
});

/* --- карточка клиента (Customer 360) -------------------------------------- */

async function loadCustomerCard(customerId, target) {
  const container = target || $("inbox-col-customer");
  if (!customerId) {
    container.innerHTML = `<div class="customer-empty">Нет карточки</div>`;
    return;
  }
  try {
    const [customer, notes, tasks] = await Promise.all([
      api(`/admin/api/customers/${customerId}`),
      api(`/admin/api/customers/${customerId}/notes`),
      api(`/admin/api/customers/${customerId}/tasks`),
    ]);
    container.innerHTML = customerCardHtml(customer, notes.items || [], tasks.items || []);
  } catch (err) {
    container.innerHTML = `<div class="customer-empty">${esc(err.message)}</div>`;
  }
}

function customerCardHtml(c, notes, tasks) {
  const channels = (c.identities || []).map((i) =>
    `${channelPill(i.channel)} <span class="muted">${esc(i.external_id)}</span>`).join("<br>");
  const tags = (c.tags || []).map((t) =>
    `<span class="tag">${esc(t.name)}<button data-untag="${esc(t.name)}" title="Снять тег">×</button></span>`).join("");
  const leadOptions = Object.entries(LEAD_LABELS)
    .filter(([key]) => key !== "none")
    .map(([key, label]) =>
      `<option value="${key}" ${c.lead_status === key ? "selected" : ""}>${label}</option>`).join("");
  const notesHtml = notes.map((n) =>
    `<div class="note">${esc(n.text)}<div class="note__meta">${esc(n.author)} · ${esc(fmtTime(n.created_at))}</div></div>`).join("");
  const tasksHtml = tasks.map((t) =>
    `<div class="task ${t.status === "done" ? "task--done" : ""}">
      ${esc(t.title)}
      <div class="task__meta">${esc(fmtTime(t.created_at))}${t.due_at ? ` · до ${esc(fmtTime(t.due_at))}` : ""}
      ${t.status === "open" ? ` · <a href="#" data-task-done="${t.id}">выполнено</a>` : ""}</div>
    </div>`).join("");
  const archived = c.status === "archived";
  return `
  <div class="c360" data-customer="${c.id}">
    <div>
      <div class="c360__name">${esc(c.name || "Без имени")}</div>
      <div class="muted">${esc(c.counts.messages)} сообщ. · ${esc(c.counts.conversations)} диалог. · с ${esc(fmtTime(c.first_seen_at))}</div>
    </div>
    <div class="c360__section">
      <h4>Контакты</h4>
      <dl class="kv">
        <dt>Имя</dt><dd><input data-field="name" value="${esc(c.name)}" /></dd>
        <dt>Телефон</dt><dd><input data-field="phone" value="${esc(c.phone)}" /></dd>
        <dt>E-mail</dt><dd><input data-field="email" value="${esc(c.email)}" /></dd>
        <dt>Username</dt><dd><input data-field="username" value="${esc(c.username)}" /></dd>
      </dl>
    </div>
    <div class="c360__section">
      <h4>Ребёнок</h4>
      <dl class="kv">
        <dt>Имя</dt><dd><input data-field="child_name" value="${esc(c.child_name)}" /></dd>
        <dt>Возраст</dt><dd><input data-field="child_age" value="${esc(c.child_age)}" /></dd>
      </dl>
    </div>
    <div class="c360__section">
      <h4>Статус</h4>
      <dl class="kv">
        <dt>Лид</dt><dd><select data-field="lead_status">${leadOptions}</select></dd>
        <dt>Менеджер</dt><dd><input data-field="manager" value="${esc(c.manager)}" /></dd>
        <dt>Интересы</dt><dd><input data-field="interests" value="${esc(c.interests)}" /></dd>
      </dl>
    </div>
    <div class="c360__section">
      <h4>Каналы</h4>
      ${channels || `<span class="muted">—</span>`}
    </div>
    <div class="c360__section">
      <h4>Теги</h4>
      <div class="tag-row">${tags}</div>
      <form class="mini-form" data-form="tag">
        <input name="name" placeholder="Новый тег" />
        <button class="btn btn--sm btn--ghost" type="submit">+</button>
      </form>
    </div>
    <div class="c360__section">
      <h4>Заметки</h4>
      ${notesHtml || `<div class="muted">Нет заметок</div>`}
      <form class="mini-form" data-form="note">
        <input name="text" placeholder="Добавить заметку" />
        <button class="btn btn--sm btn--ghost" type="submit">+</button>
      </form>
    </div>
    <div class="c360__section">
      <h4>Задачи</h4>
      ${tasksHtml || `<div class="muted">Нет задач</div>`}
      <form class="mini-form" data-form="task">
        <input name="title" placeholder="Новая задача" />
        <button class="btn btn--sm btn--ghost" type="submit">+</button>
      </form>
    </div>
    <div class="c360__section">
      <h4>Заметки о клиенте</h4>
      <dl class="kv"><dt>Заметка</dt><dd><input data-field="notes" value="${esc(c.notes)}" /></dd></dl>
    </div>
    <div class="c360__actions">
      <button class="btn btn--ghost btn--sm" data-action="timeline">Полная история</button>
      ${archived
        ? `<button class="btn btn--ghost btn--sm" data-action="unarchive">Вернуть из архива</button>`
        : `<button class="btn btn--ghost btn--sm" data-action="archive">В архив</button>
           <button class="btn btn--ghost btn--sm" data-action="merge">Объединить…</button>`}
    </div>
  </div>`;
}

/* Делегирование событий карточки: правки полей, теги, заметки, задачи. */
document.addEventListener("change", async (event) => {
  const field = event.target.closest("[data-field]");
  if (!field) return;
  const card = field.closest("[data-customer]");
  if (!card) return;
  try {
    await api(`/admin/api/customers/${card.dataset.customer}`, {
      method: "PATCH",
      body: JSON.stringify({ [field.dataset.field]: field.value }),
    });
    toast("Сохранено");
    loadInbox({ silent: true });
  } catch (err) {
    toast(err.message);
  }
});

document.addEventListener("submit", async (event) => {
  const form = event.target.closest("[data-form]");
  if (!form) return;
  event.preventDefault();
  const card = form.closest("[data-customer]");
  if (!card) return;
  const id = card.dataset.customer;
  const kind = form.dataset.form;
  const input = form.querySelector("input");
  const value = input.value.trim();
  if (!value) return;
  const urls = { tag: "tags", note: "notes", task: "tasks" };
  const bodyKey = { tag: "name", note: "text", task: "title" }[kind];
  try {
    await api(`/admin/api/customers/${id}/${urls[kind]}`, {
      method: "POST",
      body: JSON.stringify({ [bodyKey]: value }),
    });
    loadCustomerCard(Number(id));
  } catch (err) {
    toast(err.message);
  }
});

document.addEventListener("click", async (event) => {
  const untag = event.target.closest("[data-untag]");
  if (untag) {
    const card = untag.closest("[data-customer]");
    await api(`/admin/api/customers/${card.dataset.customer}/tags/${encodeURIComponent(untag.dataset.untag)}`,
      { method: "DELETE" }).catch((err) => toast(err.message));
    loadCustomerCard(Number(card.dataset.customer));
    return;
  }
  const done = event.target.closest("[data-task-done]");
  if (done) {
    event.preventDefault();
    const card = done.closest("[data-customer]");
    await api(`/admin/api/tasks/${done.dataset.taskDone}/done`, { method: "POST" })
      .catch((err) => toast(err.message));
    loadCustomerCard(Number(card.dataset.customer));
    return;
  }
  const action = event.target.closest("[data-action]");
  if (!action) return;
  const card = action.closest("[data-customer]");
  const id = Number(card.dataset.customer);
  if (action.dataset.action === "timeline") {
    openTimeline(id);
  } else if (action.dataset.action === "archive") {
    if (!confirm("Отправить клиента в архив? Данные сохранятся.")) return;
    await api(`/admin/api/customers/${id}/archive`, { method: "POST", body: "{}" }).catch((err) => toast(err.message));
    loadCustomerCard(id);
    loadInbox({ silent: true });
  } else if (action.dataset.action === "unarchive") {
    await api(`/admin/api/customers/${id}/unarchive`, { method: "POST" }).catch((err) => toast(err.message));
    loadCustomerCard(id);
  } else if (action.dataset.action === "merge") {
    const other = prompt("ID клиента-дубля, которого вливаем в эту карточку (его история переедет сюда):");
    if (!other) return;
    try {
      await api("/admin/api/customers/merge", {
        method: "POST",
        body: JSON.stringify({ primary_id: id, secondary_id: Number(other) }),
      });
      toast("Клиенты объединены");
      loadCustomerCard(id);
      loadInbox({ silent: true });
    } catch (err) {
      toast(err.message);
    }
  }
});

$("chat-customer-btn").addEventListener("click", () => {
  if (INBOX.active) openDrawer("Карточка клиента", () => loadCustomerCard(INBOX.active.customer_id, $("drawer-body")));
});

/* --- drawer и полная история ---------------------------------------------- */

function openDrawer(title, loader) {
  $("drawer").hidden = false;
  $("drawer-title").textContent = title;
  $("drawer-body").innerHTML = `<div class="empty">Загружаю…</div>`;
  loader();
}

function closeDrawer() { $("drawer").hidden = true; }
$("drawer-close").addEventListener("click", closeDrawer);
$("drawer-backdrop").addEventListener("click", closeDrawer);

async function openTimeline(customerId) {
  openDrawer("Полная история клиента", async () => {
    try {
      const data = await api(`/admin/api/customers/${customerId}/timeline`);
      const items = data.items || [];
      $("drawer-body").innerHTML = items.length ? items.map(timelineItemHtml).join("") : `<div class="empty">Пусто</div>`;
    } catch (err) {
      $("drawer-body").innerHTML = `<div class="empty">${esc(err.message)}</div>`;
    }
  });
}

function timelineItemHtml(item) {
  const when = esc(fmtTime(item.ts));
  if (item.type === "message") {
    const who = { customer: "Клиент", ai: "AI", manager: "Менеджер", system: "Система" }[item.sender_type] || item.sender_type;
    return `<div class="tl-item tl-item--message"><div class="tl-item__meta">${when} · ${esc(who)}</div>${esc(item.text)}</div>`;
  }
  if (item.type === "ai_event") {
    return `<div class="tl-item tl-item--ai_event"><div class="tl-item__meta">${when} · событие AI: ${esc(item.kind)}</div>${esc((item.detail && (item.detail.question || item.detail.reason)) || "")}</div>`;
  }
  if (item.type === "note") {
    return `<div class="tl-item tl-item--note"><div class="tl-item__meta">${when} · заметка (${esc(item.author)})</div>${esc(item.text)}</div>`;
  }
  return `<div class="tl-item tl-item--task"><div class="tl-item__meta">${when} · задача (${esc(item.status)})</div>${esc(item.title)}</div>`;
}

/* --- клиенты (список) ------------------------------------------------------ */

let CUSTOMERS_OFFSET = 0;
const CUSTOMERS_LIMIT = 30;

async function loadCustomers() {
  try {
    const params = new URLSearchParams();
    if ($("customers-search").value.trim()) params.set("search", $("customers-search").value.trim());
    if ($("customers-lead").value) params.set("lead_status", $("customers-lead").value);
    if ($("customers-archived").checked) params.set("status", "archived");
    params.set("limit", String(CUSTOMERS_LIMIT));
    params.set("offset", String(CUSTOMERS_OFFSET));
    const data = await api(`/admin/api/customers?${params}`);
    const items = data.items || [];
    $("customers-list").innerHTML = items.length ? items.map((c) => `
      <button class="customer-row" data-open-customer="${c.id}">
        <span class="avatar avatar--${esc((c.channels || [])[0] || "web")}">${esc(initials(c.name, "?"))}</span>
        <span class="customer-row__main">
          <span class="customer-row__name">${esc(c.name || "Без имени")}</span>
          <span class="customer-row__meta">
            ${esc(c.phone || "телефона нет")} · ${esc(LEAD_LABELS[c.lead_status] || c.lead_status)}
            · ${(c.channels || []).map((ch) => CHANNEL_LABEL[ch] || ch).join(", ") || "—"}
            · активен ${esc(fmtTime(c.last_seen_at))}
          </span>
        </span>
        ${c.child_name ? `<span class="pill">${esc(c.child_name)}${c.child_age ? `, ${esc(c.child_age)}` : ""}</span>` : ""}
      </button>`).join("") : `<div class="empty">Никого не нашлось</div>`;
    const page = Math.floor(CUSTOMERS_OFFSET / CUSTOMERS_LIMIT) + 1;
    const pages = Math.max(1, Math.ceil((data.total || 0) / CUSTOMERS_LIMIT));
    $("customers-page").textContent = `${page} / ${pages} (всего ${data.total || 0})`;
    $("customers-prev").disabled = CUSTOMERS_OFFSET === 0;
    $("customers-next").disabled = CUSTOMERS_OFFSET + CUSTOMERS_LIMIT >= (data.total || 0);
  } catch (err) {
    toast(err.message);
  }
}

$("customers-search").addEventListener("input", () => { CUSTOMERS_OFFSET = 0; loadCustomers(); });
$("customers-lead").addEventListener("change", () => { CUSTOMERS_OFFSET = 0; loadCustomers(); });
$("customers-archived").addEventListener("change", () => { CUSTOMERS_OFFSET = 0; loadCustomers(); });
$("customers-prev").addEventListener("click", () => { CUSTOMERS_OFFSET = Math.max(0, CUSTOMERS_OFFSET - CUSTOMERS_LIMIT); loadCustomers(); });
$("customers-next").addEventListener("click", () => { CUSTOMERS_OFFSET += CUSTOMERS_LIMIT; loadCustomers(); });

$("customers-list").addEventListener("click", (event) => {
  const row = event.target.closest("[data-open-customer]");
  if (!row) return;
  openCustomerById(Number(row.dataset.openCustomer));
});

/* Адаптер для deep links и переходов из других разделов. */
function openCustomerById(id) {
  if (!id) return;
  setHash("#/customers/" + id);
  openDrawer("Карточка клиента", () => loadCustomerCard(id, $("drawer-body")));
}

/* --- заявки (позвать администратора / лид с сайта) -------------------------- */

const REQ_STATUS_LABELS = {
  new: "Новая", in_progress: "В работе", contacted: "Связались",
  waiting: "Ожидает", resolved: "Решена", cancelled: "Отменена",
};
const REQ_KIND_LABELS = { admin_request: "Администратор", lead: "Заявка с сайта" };
const REQ_TABS = [
  ["new", "Новые"],
  ["in_progress", "В работе"],
  ["pending", "Ожидают"],
  ["done", "Завершённые"],
  ["all", "Все"],
];
const REQ_TAB_STATUSES = {
  new: ["new"], in_progress: ["in_progress"],
  pending: ["waiting", "contacted"], done: ["resolved", "cancelled"], all: [],
};
const REQUESTS = { items: [], counts: {}, tab: "new" };

function reqStatusPill(status) {
  const cls = { new: "pill--req-new", in_progress: "pill--lead", resolved: "pill--ai",
    cancelled: "pill--paused" }[status] || "";
  return `<span class="pill ${cls}">${esc(REQ_STATUS_LABELS[status] || status)}</span>`;
}

function reqContact(r) {
  let contact = {};
  try { contact = JSON.parse(r.contact_json || "{}"); } catch (_) { /* игнор */ }
  return contact;
}

function requestRowHtml(r) {
  const contact = reqContact(r);
  const name = r.display_name || r.name || contact.name || contact.fio_parent || r.phone || contact.phone || `Клиент #${r.customer_id || "—"}`;
  const isNew = r.status === "new";
  return `
    <button class="customer-row req-row ${isNew ? "req-row--new" : ""}" data-req="${r.id}">
      <span class="avatar avatar--${esc(r.channel || "web")}">${esc(initials(name, CHANNEL_LABEL[r.channel]))}</span>
      <span class="customer-row__main">
        <span class="customer-row__name">
          <span class="muted">#${esc(r.id)}</span> ${esc(name)}
          ${isNew ? `<span class="unread-badge">new</span>` : ""}
        </span>
        <span class="customer-row__meta">
          ${channelPill(r.channel)} <span class="pill">${esc(REQ_KIND_LABELS[r.kind] || r.kind)}</span>
          ${esc((r.reason || "").slice(0, 90))}${(r.reason || "").length > 90 ? "…" : ""}
        </span>
        <span class="customer-row__meta">
          ${esc(fmtTime(r.created_at))}${r.manager ? ` · ${esc(r.manager)}` : ""}
        </span>
      </span>
      ${reqStatusPill(r.status)}
    </button>`;
}

async function loadRequests(options = {}) {
  try {
    const data = await api("/admin/api/requests?limit=200");
    REQUESTS.items = data.items || [];
    REQUESTS.counts = data.counts || {};
    const newCount = REQUESTS.counts.new || 0;
    $("nav-requests").hidden = !newCount;
    $("nav-requests").textContent = newCount || "";
    renderRequestTabs();
    renderRequestList();
  } catch (err) {
    if (!options.silent) {
      if (err.message === "unauthorized") showGate("Токен больше не подходит");
      else toast(err.message);
    }
  }
}

function renderRequestTabs() {
  const c = REQUESTS.counts;
  const tabCounts = {
    new: c.new || 0,
    in_progress: c.in_progress || 0,
    pending: (c.waiting || 0) + (c.contacted || 0),
    done: (c.resolved || 0) + (c.cancelled || 0),
    all: c.total || 0,
  };
  $("req-tabs").innerHTML = REQ_TABS.map(([key, label]) =>
    `<button class="req-tab ${REQUESTS.tab === key ? "req-tab--active" : ""}" data-req-tab="${key}">
      ${label} <span class="req-tab__count">${tabCounts[key]}</span></button>`).join("");
}

function renderRequestList() {
  const statuses = REQ_TAB_STATUSES[REQUESTS.tab] || [];
  const items = statuses.length
    ? REQUESTS.items.filter((r) => statuses.includes(r.status))
    : REQUESTS.items;
  $("requests-list").innerHTML = items.length
    ? items.map(requestRowHtml).join("")
    : `<div class="empty">Заявок нет</div>`;
}

$("req-tabs").addEventListener("click", (event) => {
  const tab = event.target.closest("[data-req-tab]");
  if (!tab) return;
  REQUESTS.tab = tab.dataset.reqTab;
  renderRequestTabs();
  renderRequestList();
});

$("requests-list").addEventListener("click", (event) => {
  const row = event.target.closest("[data-req]");
  if (row) openRequest(Number(row.dataset.req));
});

/* --- карточка заявки (drawer) ------------------------------------------------ */

async function openRequest(id) {
  if (!id) return;
  setHash("#/requests/" + id);
  if (SECTION !== "requests") showSection("requests", { keepHash: true });
  openDrawer(`Заявка #${id}`, async () => {
    try {
      const data = await api(`/admin/api/requests/${id}`);
      renderRequestDetail(data);
    } catch (err) {
      $("drawer-body").innerHTML = `<div class="empty">${esc(err.message)}</div>`;
    }
  });
}

function renderRequestDetail(data) {
  const r = data.request || {};
  const customer = data.customer || null;
  const conv = data.conversation || null;
  const messages = data.recent_messages || [];
  const contact = reqContact(r);
  const name = r.display_name || r.name || contact.name || contact.fio_parent || (customer && customer.name) || "Без имени";
  const phone = r.phone || contact.phone || (customer && customer.phone) || "";
  const email = contact.email || (customer && customer.email) || "";
  const username = contact.username || (customer && customer.username) || "";
  const lastIn = [...messages].reverse().find((m) => m.direction === "in");
  const statusOptions = Object.entries(REQ_STATUS_LABELS).map(([key, label]) =>
    `<option value="${key}" ${r.status === key ? "selected" : ""}>${label}</option>`).join("");
  const history = messages.map((m) => {
    const who = { customer: "Клиент", ai: "AI", manager: "Менеджер", system: "Система" }[m.sender_type] || m.sender_type;
    return `<div class="tl-item tl-item--message">
      <div class="tl-item__meta">${esc(fmtTime(m.created_at))} · ${esc(who)}</div>${esc(m.text)}</div>`;
  }).join("");
  $("drawer-body").innerHTML = `
  <div class="c360 req-card" data-req-id="${r.id}" data-conv-id="${r.conversation_id || (conv && conv.id) || ""}"
       data-customer-id="${r.customer_id || ""}">
    <div>
      <div class="c360__name">Заявка #${esc(r.id)} ${reqStatusPill(r.status)}</div>
      <div class="muted">создана ${esc(fmtTime(r.created_at))}${r.updated_at ? ` · обновлена ${esc(fmtTime(r.updated_at))}` : ""}</div>
    </div>
    <div class="c360__section">
      <h4>Клиент</h4>
      <dl class="kv">
        <dt>Имя</dt><dd>${esc(name)}</dd>
        <dt>Телефон</dt><dd>${phone
          ? `<a href="tel:${esc(phone)}">${esc(phone)}</a>
             <a class="btn btn--sm btn--ghost" href="tel:${esc(phone)}">Позвонить</a>
             <button class="btn btn--sm btn--ghost" data-copy="${esc(phone)}">Скопировать</button>`
          : `<span class="muted">Телефон не указан</span>`}</dd>
        ${email ? `<dt>E-mail</dt><dd><a href="mailto:${esc(email)}">${esc(email)}</a>
          <button class="btn btn--sm btn--ghost" data-copy="${esc(email)}">Скопировать</button></dd>` : ""}
        ${username ? `<dt>Telegram</dt><dd>${esc("@" + String(username).replace(/^@/, ""))}</dd>` : ""}
        ${contact.fio_child ? `<dt>Ребёнок</dt><dd>${esc(contact.fio_child)}${contact.birthday ? `, ${esc(contact.birthday)}` : ""}</dd>` : ""}
        ${contact.course ? `<dt>Курс</dt><dd>${esc(contact.course)}</dd>` : ""}
        ${contact.branch ? `<dt>Филиал</dt><dd>${esc(contact.branch)}</dd>` : ""}
        <dt>Канал</dt><dd>${channelPill(r.channel)} ${esc(REQ_KIND_LABELS[r.kind] || r.kind || "")}</dd>
        ${conv && conv.external_user_id ? `<dt>ID канала</dt><dd class="muted">${esc(conv.external_user_id)}</dd>` : ""}
      </dl>
    </div>
    <div class="c360__section">
      <h4>Обращение</h4>
      <dl class="kv">
        <dt>Причина</dt><dd>${esc(r.reason || "—")}</dd>
        ${r.source ? `<dt>Источник</dt><dd>${esc(r.source)}</dd>` : ""}
        <dt>Последнее сообщение</dt><dd>${lastIn ? esc(lastIn.text) : "—"}</dd>
      </dl>
    </div>
    <div class="c360__section">
      <h4>Статус и ответственный</h4>
      <dl class="kv">
        <dt>Статус</dt><dd><select data-req-status>${statusOptions}</select></dd>
        <dt>Менеджер</dt><dd>${esc(r.manager || "—")}</dd>
      </dl>
    </div>
    <div class="c360__actions">
      ${r.conversation_id ? `<button class="btn btn--sm" data-req-action="open-chat">Открыть чат</button>` : ""}
      ${r.customer_id ? `<button class="btn btn--sm btn--ghost" data-req-action="open-customer">Открыть клиента</button>` : ""}
      <button class="btn btn--sm btn--ghost" data-req-action="take">Взять в работу</button>
      <button class="btn btn--sm btn--ghost" data-req-action="assign">Назначить менеджера…</button>
      ${r.status !== "resolved" ? `<button class="btn btn--sm btn--ghost" data-req-action="resolve">Завершить</button>` : ""}
    </div>
    <div class="c360__section">
      <h4>Комментарий менеджера</h4>
      <textarea id="req-notes" rows="3" placeholder="Заметки по заявке">${esc(r.notes || "")}</textarea>
      <div class="actions" style="margin-top:8px">
        <button class="btn btn--sm" data-req-action="save-notes">Сохранить комментарий</button>
      </div>
    </div>
    <div class="c360__section">
      <h4>История разговора</h4>
      ${history || `<div class="muted">Сообщений нет</div>`}
      ${r.conversation_id ? `<div class="actions" style="margin-top:8px">
        <button class="btn btn--sm btn--ghost" data-req-action="open-chat">Открыть полный диалог</button>
      </div>` : ""}
    </div>
  </div>`;
}

async function reqRefresh(id) {
  loadRequests({ silent: true });
  openRequest(id);
}

/* Действия карточки заявки — делегирование из drawer. */
$("drawer-body").addEventListener("click", async (event) => {
  const action = event.target.closest("[data-req-action]");
  if (!action) return;
  const card = action.closest("[data-req-id]");
  if (!card) return;
  const id = Number(card.dataset.reqId);
  const convId = Number(card.dataset.convId) || 0;
  const customerId = Number(card.dataset.customerId) || 0;
  const kind = action.dataset.reqAction;
  try {
    if (kind === "open-chat") {
      closeDrawer();
      showSection("inbox");
      openConversationById(convId);
      return;
    }
    if (kind === "open-customer") {
      openCustomerById(customerId);
      return;
    }
    if (kind === "take") {
      const manager = (SESSION && SESSION.username) || prompt("Ваше имя для поля «ответственный»:");
      await api(`/admin/api/requests/${id}/status`, {
        method: "POST", body: JSON.stringify({ status: "in_progress" }) });
      if (manager) {
        await api(`/admin/api/requests/${id}/assign`, {
          method: "POST", body: JSON.stringify({ manager }) });
      }
      toast("Заявка в работе");
    } else if (kind === "assign") {
      const manager = prompt("Имя менеджера:", (SESSION && SESSION.username) || "");
      if (!manager) return;
      await api(`/admin/api/requests/${id}/assign`, {
        method: "POST", body: JSON.stringify({ manager }) });
      toast("Менеджер назначен");
    } else if (kind === "resolve") {
      if (!confirm("Завершить заявку? Статус станет «Решена».")) return;
      await api(`/admin/api/requests/${id}/status`, {
        method: "POST", body: JSON.stringify({ status: "resolved" }) });
      toast("Заявка завершена");
    } else if (kind === "save-notes") {
      await api(`/admin/api/requests/${id}/notes`, {
        method: "POST", body: JSON.stringify({ notes: $("req-notes").value }) });
      toast("Комментарий сохранён");
    }
    reqRefresh(id);
  } catch (err) {
    toast(err.message);
  }
});

$("drawer-body").addEventListener("change", async (event) => {
  const select = event.target.closest("[data-req-status]");
  if (!select) return;
  const card = select.closest("[data-req-id]");
  if (!card) return;
  const id = Number(card.dataset.reqId);
  try {
    await api(`/admin/api/requests/${id}/status`, {
      method: "POST", body: JSON.stringify({ status: select.value }) });
    toast("Статус обновлён");
    reqRefresh(id);
  } catch (err) {
    toast(err.message);
  }
});

/* Копирование контактов (карточка заявки, предупреждение о доставке). */
document.addEventListener("click", (event) => {
  const btn = event.target.closest("[data-copy]");
  if (!btn) return;
  const value = btn.dataset.copy;
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(value).then(() => toast("Скопировано")).catch(() => toast(value));
  } else {
    toast(value);
  }
});

/* --- глобальный поиск (Ctrl+K) -------------------------------------------- */

document.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    $("global-search").focus();
  }
  if (event.key === "Escape") {
    $("search-results").hidden = true;
    closeDrawer();
  }
});

let searchTimer = null;
$("global-search").addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(runGlobalSearch, 300);
});

async function runGlobalSearch() {
  const needle = $("global-search").value.trim();
  const box = $("search-results");
  if (needle.length < 2) {
    box.hidden = true;
    return;
  }
  try {
    const [customers, messages] = await Promise.all([
      api(`/admin/api/customers?search=${encodeURIComponent(needle)}&limit=5`),
      api(`/admin/api/inbox?q=${encodeURIComponent(needle)}&limit=5`),
    ]);
    const rows = [];
    (customers.items || []).forEach((c) => rows.push(
      `<button class="sr" data-open-customer="${c.id}"><b>${esc(c.name || "Без имени")}</b> <span class="muted">${esc(c.phone || "")} · клиент</span></button>`));
    (messages.items || []).forEach((item) => rows.push(
      `<button class="sr" data-conv="${item.id}"><b>${esc(item.customer_name || item.external_user_id)}</b> <span class="muted">${esc((item.last_message_text || "").slice(0, 80))}</span></button>`));
    box.innerHTML = rows.length ? rows.join("") : `<div class="empty">Ничего не найдено</div>`;
    box.hidden = false;
  } catch (err) {
    box.hidden = true;
  }
}

$("search-results").addEventListener("click", (event) => {
  $("search-results").hidden = true;
  const customerRow = event.target.closest("[data-open-customer]");
  if (customerRow) {
    openCustomerById(Number(customerRow.dataset.openCustomer));
    return;
  }
  const convRow = event.target.closest("[data-conv]");
  if (convRow) {
    showSection("inbox");
    // Диалог может не попасть в текущую выдачу фильтров — сбрасываем их
    // внутри openConversationById.
    openConversationById(Number(convRow.dataset.conv));
  }
});

document.addEventListener("click", (event) => {
  if (!event.target.closest(".topbar__search")) $("search-results").hidden = true;
});

/* --- Broadcast Center ------------------------------------------------------ */

const BC = { list: [], activeId: 0, rules: [], segments: [], pollTimer: null };

function bcStatusPill(status) {
  const labels = { draft: "Черновик", sending: "Отправляется", done: "Завершена", failed: "Ошибка" };
  const cls = status === "done" ? "pill--ai" : (status === "sending" ? "pill--lead" : "pill");
  return `<span class="pill ${cls}">${esc(labels[status] || status)}</span>`;
}

async function loadBroadcastCenter() {
  try {
    const [history, segments] = await Promise.all([
      api("/admin/api/broadcasts"),
      api("/admin/api/segments"),
    ]);
    BC.list = history.items || [];
    BC.segments = segments.items || [];
    renderBroadcastList();
    if (BC.activeId) loadBroadcastDetail(BC.activeId);
  } catch (err) {
    toast(err.message);
  }
}

function renderBroadcastList() {
    $("bc-list").innerHTML = BC.list.length ? BC.list.map((b) => `
      <button class="bc-item ${b.id === BC.activeId ? "bc-item--active" : ""}" data-bc="${b.id}">
        <span class="bc-item__title">${esc(b.title || "Без названия")}</span>
        <span class="bc-item__meta">
          ${bcStatusPill(b.status)}
          ${esc(fmtTime(b.created_at))} · ${esc(b.delivered)}/${esc(b.total)} доставлено
          ${b.failed_count ? ` · ошибок ${esc(b.failed_count)}` : ""}
          ${b.skipped ? ` · пропущено ${esc(b.skipped)}` : ""}
        </span>
      </button>`).join("") : `<div class="empty">Рассылок ещё не было</div>`;
}

$("bc-list").addEventListener("click", (event) => {
  const item = event.target.closest("[data-bc]");
  if (!item) return;
  BC.activeId = Number(item.dataset.bc);
  renderBroadcastList();
  loadBroadcastDetail(BC.activeId);
});

const BC_FIELDS = [
  ["channel", "Канал"], ["lead_status", "Статус лида"], ["tag", "Тег"],
  ["child_age", "Возраст ребёнка"], ["date_first_seen", "Первый визит (от)"],
  ["date_last_seen", "Был активен (от)"], ["course", "Курс/интерес"],
  ["branch", "Филиал"], ["search", "Поиск по имени/телефону"],
];
const BC_OPS = [["eq", "="], ["contains", "содержит"], ["gte", ">="], ["lte", "<="]];

function ruleRowHtml(rule) {
  const fieldOptions = BC_FIELDS.map(([v, l]) =>
    `<option value="${v}" ${rule.field === v ? "selected" : ""}>${l}</option>`).join("");
  const opOptions = BC_OPS.map(([v, l]) =>
    `<option value="${v}" ${rule.op === v ? "selected" : ""}>${l}</option>`).join("");
  return `
    <div class="builder-row">
      <select data-rule-field>${fieldOptions}</select>
      <select data-rule-op>${opOptions}</select>
      <input data-rule-value placeholder="Значение" value="${esc(rule.value || "")}" />
      <button class="btn btn--sm btn--ghost" data-rule-del type="button">×</button>
    </div>`;
}

function collectRules() {
  return [...document.querySelectorAll("#bc-rules .builder-row")].map((row) => ({
    field: row.querySelector("[data-rule-field]").value,
    op: row.querySelector("[data-rule-op]").value,
    value: row.querySelector("[data-rule-value]").value.trim(),
  })).filter((rule) => rule.field && String(rule.value).length);
}

function renderBroadcastForm() {
  const segmentOptions = BC.segments.map((s) =>
    `<option value="${s.id}">${esc(s.name)}</option>`).join("");
  $("bc-main").innerHTML = `
    <h3>Новая рассылка</h3>
    <label class="field"><span>Название</span><input id="bc-title" placeholder="Например: Осенний набор" /></label>
    <label class="field"><span>Текст сообщения</span><textarea id="bc-body" rows="5" placeholder="Что отправить клиентам"></textarea></label>
    <div class="field">
      <span>Сохранённый сегмент</span>
      <div class="builder-row">
        <select id="bc-segment"><option value="">— собрать условия ниже —</option>${segmentOptions}</select>
      </div>
    </div>
    <div class="field">
      <span>Условия (все одновременно; пусто — все клиенты с MAX/Telegram)</span>
      <div id="bc-rules"></div>
      <button class="btn btn--sm btn--ghost" id="bc-rule-add" type="button">+ условие</button>
    </div>
    <div class="builder-row">
      <input id="bc-segment-name" placeholder="Имя, чтобы сохранить сегмент" />
      <button class="btn btn--sm btn--ghost" id="bc-segment-save" type="button">Сохранить сегмент</button>
    </div>
    <div class="actions" style="margin-top:12px">
      <button class="btn btn--ghost" id="bc-preview">Предпросмотр</button>
      <button class="btn btn--danger" id="bc-launch">Отправить…</button>
    </div>
    <div id="bc-preview-box"></div>`;
  BC.rules = [];
  addRuleRow();
  $("bc-rule-add").addEventListener("click", () => addRuleRow());
  $("bc-rules").addEventListener("click", (event) => {
    const del = event.target.closest("[data-rule-del]");
    if (del) del.closest(".builder-row").remove();
  });
  $("bc-segment").addEventListener("change", () => {
    const segment = BC.segments.find((s) => s.id === Number($("bc-segment").value));
    if (!segment) return;
    $("bc-rules").innerHTML = "";
    (segment.rules.length ? segment.rules : [{}]).forEach((rule) => addRuleRow(rule));
  });
  $("bc-segment-save").addEventListener("click", saveSegmentFromForm);
  $("bc-preview").addEventListener("click", previewBroadcast);
  $("bc-launch").addEventListener("click", launchBroadcast);
}

function addRuleRow(rule = {}) {
  $("bc-rules").insertAdjacentHTML("beforeend", ruleRowHtml(rule));
}

async function saveSegmentFromForm() {
  const name = $("bc-segment-name").value.trim();
  if (!name) {
    toast("Введите имя сегмента");
    return;
  }
  try {
    await api("/admin/api/segments", {
      method: "POST",
      body: JSON.stringify({ name, rules: collectRules() }),
    });
    toast("Сегмент сохранён");
    const segments = await api("/admin/api/segments");
    BC.segments = segments.items || [];
    renderBroadcastForm();
  } catch (err) {
    toast(err.message);
  }
}

async function previewBroadcast() {
  try {
    const data = await api("/admin/api/broadcasts/preview", {
      method: "POST",
      body: JSON.stringify({ rules: collectRules() }),
    });
    const byChannel = Object.entries(data.by_channel || {})
      .map(([ch, n]) => `${CHANNEL_LABEL[ch] || ch}: ${n}`).join(", ") || "0";
    const sample = (data.sample || []).map((rec) =>
      `<div>${esc(rec.name || "Без имени")} ${channelPill(rec.channel)}</div>`).join("");
    $("bc-preview-box").innerHTML = `
      <div class="preview-box">
        <b>Получателей: ${esc(data.total)}</b> (${esc(byChannel)}${data.skipped_web ? `, пропущено web: ${esc(data.skipped_web)}` : ""})
        ${sample ? `<div style="margin-top:8px">${sample}</div>` : ""}
      </div>`;
    return data;
  } catch (err) {
    toast(err.message);
    return null;
  }
}

function confirmModal(title, bodyHtml) {
  return new Promise((resolve) => {
    $("modal-title").textContent = title;
    $("modal-body").innerHTML = bodyHtml;
    $("modal").hidden = false;
    $("modal-ok").onclick = () => { $("modal").hidden = true; resolve(true); };
    $("modal-cancel").onclick = () => { $("modal").hidden = true; resolve(false); };
    $("modal-backdrop").onclick = () => { $("modal").hidden = true; resolve(false); };
  });
}

async function launchBroadcast() {
  const text = $("bc-body").value.trim();
  if (!text) {
    toast("Сначала напишите текст");
    return;
  }
  const preview = await previewBroadcast();
  if (!preview) return;
  if (!preview.total) {
    toast("По этим условиям получателей нет");
    return;
  }
  const ok = await confirmModal(
    "Отправить рассылку?",
    `<p>Получателей: <b>${esc(preview.total)}</b>
     (${Object.entries(preview.by_channel || {}).map(([ch, n]) => `${CHANNEL_LABEL[ch] || ch}: ${n}`).join(", ")})
     ${preview.skipped_web ? `<br>Пропущено web-клиентов: ${esc(preview.skipped_web)} (у виджета нет push)` : ""}</p>
     <p class="muted">Отменить после запуска будет нельзя.</p>`);
  if (!ok) return;
  try {
    const created = await api("/admin/api/broadcasts", {
      method: "POST",
      body: JSON.stringify({
        title: $("bc-title").value.trim(),
        text,
        rules: collectRules(),
      }),
    });
    await api(`/admin/api/broadcasts/${created.id}/send`, {
      method: "POST",
      body: JSON.stringify({ confirm: true }),
    });
    toast("Рассылка запущена");
    BC.activeId = created.id;
    loadBroadcastCenter();
    watchBroadcast(created.id);
  } catch (err) {
    toast(err.message);
  }
}

function watchBroadcast(id) {
  clearInterval(BC.pollTimer);
  BC.pollTimer = setInterval(async () => {
    try {
      const detail = await api(`/admin/api/broadcasts/${id}`);
      renderBroadcastDetail(detail);
      if (detail.status !== "sending") {
        clearInterval(BC.pollTimer);
        loadBroadcastCenter();
      }
    } catch (err) {
      clearInterval(BC.pollTimer);
    }
  }, 3000);
}

async function loadBroadcastDetail(id) {
  try {
    const detail = await api(`/admin/api/broadcasts/${id}`);
    renderBroadcastDetail(detail);
    if (detail.status === "sending") watchBroadcast(id);
  } catch (err) {
    $("bc-main").innerHTML = `<div class="empty">${esc(err.message)}</div>`;
  }
}

function renderBroadcastDetail(b) {
  const recipients = b.recipients || [];
  const rows = recipients.map((r) => `
    <tr>
      <td>${esc(r.customer_name || "Без имени")}</td>
      <td>${channelPill(r.channel)}</td>
      <td>${esc(r.status)}${r.error ? `<div class="muted">${esc(r.error)}</div>` : ""}</td>
      <td>${esc(fmtTime(r.sent_at))}</td>
      <td>${r.status === "failed" ? `<button class="btn btn--sm btn--ghost" data-retry="${r.id}">Повторить (${r.retry_count}/3)</button>` : ""}</td>
    </tr>`).join("");
  $("bc-main").innerHTML = `
    <h3>${esc(b.title || "Рассылка")}</h3>
    <div>${bcStatusPill(b.status)} <span class="muted">создана ${esc(fmtTime(b.created_at))}${b.finished_at ? `, завершена ${esc(fmtTime(b.finished_at))}` : ""}</span></div>
    <div class="bc-stats">
      <span class="bc-stat">Всего: <b>${esc(b.total)}</b></span>
      <span class="bc-stat">Доставлено: <b>${esc(b.delivered)}</b></span>
      <span class="bc-stat">Ошибок: <b>${esc(b.failed_count)}</b></span>
      <span class="bc-stat">Пропущено: <b>${esc(b.skipped)}</b></span>
    </div>
    <div class="field"><span>Текст</span><div class="preview-box">${esc(b.text)}</div></div>
    <div class="builder-row" style="margin-top:12px">
      <select id="bc-rec-filter">
        <option value="">Все получатели</option>
        <option value="sent">Доставленные</option>
        <option value="failed">Ошибки</option>
        <option value="pending">В очереди</option>
      </select>
    </div>
    <table class="rec-table">
      <thead><tr><th>Клиент</th><th>Канал</th><th>Статус</th><th>Когда</th><th></th></tr></thead>
      <tbody>${rows || `<tr><td colspan="5" class="muted">Получателей нет</td></tr>`}</tbody>
    </table>`;
  $("bc-rec-filter").addEventListener("change", async () => {
    const status = $("bc-rec-filter").value;
    const detail = await api(`/admin/api/broadcasts/${b.id}${status ? `?status=${status}` : ""}`);
    renderBroadcastDetail(detail);
    $("bc-rec-filter").value = status;
  });
}

$("bc-main").addEventListener("click", async (event) => {
  const retry = event.target.closest("[data-retry]");
  if (!retry) return;
  retry.disabled = true;
  try {
    const result = await api(`/admin/api/broadcasts/${BC.activeId}/recipients/${retry.dataset.retry}/retry`,
      { method: "POST", body: "{}" });
    toast(result.ok ? "Переотправлено" : `Снова ошибка: ${result.error || ""}`);
  } catch (err) {
    toast(err.message);
  }
  loadBroadcastDetail(BC.activeId);
});

$("bc-new").addEventListener("click", () => {
  BC.activeId = 0;
  renderBroadcastList();
  renderBroadcastForm();
});

/* --- воронка (kanban) ------------------------------------------------------- */

async function loadPipeline() {
  try {
    const data = await api("/admin/api/pipeline");
    renderKanban(data);
  } catch (err) {
    toast(err.message);
  }
}

function renderKanban(data) {
  $("kanban").innerHTML = (data.stages || []).map((stage) => {
    const cards = (data.board[stage] || []).map((c) => `
      <div class="kanban__card" draggable="true" data-card="${c.id}">
        <div><b>${esc(c.name || "Без имени")}</b></div>
        <div class="muted">${esc(CHANNEL_LABEL[c.channel] || c.channel || "—")} · ${esc(c.interests || "")}</div>
        <div class="muted">${esc(fmtTime(c.last_message_at || c.last_seen_at))}${c.manager ? ` · ${esc(c.manager)}` : ""}</div>
      </div>`).join("");
    return `
      <div class="kanban__col" data-stage="${stage}">
        <div class="kanban__head">${esc(LEAD_LABELS[stage] || stage)}<span class="kanban__count">${(data.board[stage] || []).length}</span></div>
        ${cards}
      </div>`;
  }).join("");
}

let dragCardId = null;

$("kanban").addEventListener("dragstart", (event) => {
  const card = event.target.closest("[data-card]");
  if (card) dragCardId = Number(card.dataset.card);
});
$("kanban").addEventListener("dragover", (event) => {
  const col = event.target.closest("[data-stage]");
  if (col) {
    event.preventDefault();
    col.classList.add("kanban__col--over");
  }
});
$("kanban").addEventListener("dragleave", (event) => {
  const col = event.target.closest("[data-stage]");
  if (col) col.classList.remove("kanban__col--over");
});
$("kanban").addEventListener("drop", async (event) => {
  const col = event.target.closest("[data-stage]");
  if (!col || !dragCardId) return;
  event.preventDefault();
  col.classList.remove("kanban__col--over");
  try {
    await api(`/admin/api/customers/${dragCardId}`, {
      method: "PATCH",
      body: JSON.stringify({ lead_status: col.dataset.stage }),
    });
    toast("Статус обновлён");
  } catch (err) {
    toast(err.message);
  }
  dragCardId = null;
  loadPipeline();
});
$("kanban").addEventListener("click", (event) => {
  const card = event.target.closest("[data-card]");
  if (card) openCustomerById(Number(card.dataset.card));
});

/* --- экспорт CSV ------------------------------------------------------------ */

async function downloadCsv(path, filename) {
  try {
    const resp = await fetch(path, { headers: { "X-Admin-Token": TOKEN } });
    if (!resp.ok) throw new Error(`Сервер ответил ${resp.status}`);
    const blob = await resp.blob();
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    link.click();
    URL.revokeObjectURL(link.href);
  } catch (err) {
    toast(err.message);
  }
}

$("export-customers").addEventListener("click", () =>
  downloadCsv("/admin/api/export/customers.csv", "customers.csv"));
$("export-messages").addEventListener("click", () =>
  downloadCsv("/admin/api/export/messages.csv", "messages.csv"));


/* --- вопросы и AI-события --------------------------------------------------- */

async function loadInsights() {
  try {
    const data = await api("/admin/insights?days=30");
    const items = data.top_questions || data.rows || [];
    $("insights").innerHTML = items.length
      ? items.map((item) => `
          <div class="insight">
            <div>${esc(item.question || item.text || "")}</div>
            <div class="muted">${esc(item.count ? `${item.count} раз` : "")} ${esc(item.at || "")}</div>
            <button class="btn btn--sm btn--ghost" data-kb-add="${esc(item.question || item.text || "")}">В базу знаний</button>
          </div>`).join("")
      : `<div class="empty">За 30 дней бот не спасовал ни разу.</div>`;
  } catch (err) {
    $("insights").innerHTML = `<div class="empty">${esc(err.message)}</div>`;
  }
  try {
    const events = await api("/admin/api/ai/events?days=7");
    const items = events.items || [];
    $("ai-events").innerHTML = items.length
      ? items.map((e) => `
          <div class="ai-event">
            <span class="pill pill--paused">${esc(e.kind)}</span>
            <span class="muted"> ${esc(fmtTime(e.created_at))}</span>
            <div>${esc((JSON.parse(e.detail_json || "{}").question) || (JSON.parse(e.detail_json || "{}").reason) || "")}</div>
          </div>`).join("")
      : `<div class="empty">Событий нет.</div>`;
  } catch (err) {
    $("ai-events").innerHTML = `<div class="empty">${esc(err.message)}</div>`;
  }
}

/* --- настройки -------------------------------------------------------------- */

async function loadSettings() {
  try {
    const h = await api("/admin/api/system");
    const ev = h.inbound_24h || {};
    const mb = h.db_size_bytes ? (h.db_size_bytes / 1048576).toFixed(1) + " МБ" : "—";
    $("settings-health").innerHTML = `
      <p>База данных: <b>${h.db_ok ? "в порядке" : "ошибка"}</b> (${esc(mb)})</p>
      <p>MAX: <b>${h.max_ok ? "настроен" : "нет токена"}</b> ·
         Telegram: <b>${h.telegram_ok ? "настроен" : "нет токена"}</b> ·
         Веб-виджет: <b>${h.web_ok ? "работает" : "—"}</b> ·
         AI: <b>${h.ai_ok ? esc(h.llm_model) : "нет ключа"}</b></p>
      <p class="muted">Процесс работает с ${esc(fmtTime(h.started_at))}
         (uptime ${esc(Math.round(h.process_uptime_sec / 60))} мин).</p>
      <p class="muted">Ingestion за 24ч: обработано ${esc(ev.processed || 0)},
         получено ${esc(ev.received || 0)}, ошибок ${esc(ev.failed || 0)},
         дублей ${esc(ev.duplicate || 0)}.</p>`;
  } catch (err) {
    $("settings-health").innerHTML = `<div class="empty">${esc(err.message)}</div>`;
  }
}

/* --- аналитика -------------------------------------------------------------- */

function barChart(rows, labels) {
  /* Простейший SVG bar-chart без библиотек: столбцы по дням. */
  if (!rows.length) return `<div class="empty">Нет данных за период</div>`;
  const max = Math.max(...rows.map((r) => r.value), 1);
  const w = Math.max(18, Math.floor(560 / rows.length) - 4);
  const bars = rows.map((r, i) => {
    const h = Math.max(2, Math.round((r.value / max) * 120));
    return `<g><rect x="${i * (w + 4)}" y="${124 - h}" width="${w}" height="${h}" rx="3" fill="#f59e0b">
      <title>${esc(labels[i])}: ${esc(r.value)}</title></rect></g>`;
  }).join("");
  return `<svg viewBox="0 0 ${rows.length * (w + 4)} 140" style="width:100%;height:150px">${bars}</svg>`;
}

async function loadAnalytics() {
  try {
    const days = $("analytics-days").value;
    const data = await api(`/admin/api/analytics?days=${days}`);
    const ai = data.ai || {};
    $("an-cards").innerHTML = [
      [data.leads.new_in_period, "Новые клиенты за период"],
      [ai.ai_messages ?? 0, "Ответов AI"],
      [ai.manager_messages ?? 0, "Ответов менеджеров"],
      [ai.ai_share != null ? `${Math.round(ai.ai_share * 100)}%` : "—", "Доля ответов AI"],
      [ai.handoff ?? 0, "Передач менеджеру"],
      [ai.no_answer ?? 0, "Без ответа"],
      [ai.avg_conversation_length ?? 0, "Ср. длина диалога (сообщ.)"],
      [ai.repeat_customers ?? 0, "Повторные обращения"],
      [`${data.broadcasts.delivered}/${data.broadcasts.total}`, "Рассылки: доставлено/всего"],
    ].map(([v, l]) => `<div class="card"><div class="card__value">${esc(v)}</div><div class="card__label">${esc(l)}</div></div>`).join("");

    const custRows = (data.daily.customers || []).map((r) => ({ value: r.c }));
    $("an-customers-chart").innerHTML = barChart(custRows, (data.daily.customers || []).map((r) => r.day));
    const byDay = {};
    (data.daily.messages || []).forEach((r) => { byDay[r.day] = (byDay[r.day] || 0) + r.c; });
    const msgDays = Object.keys(byDay).sort();
    $("an-messages-chart").innerHTML = barChart(msgDays.map((d) => ({ value: byDay[d] })), msgDays);

    const convs = Object.fromEntries((data.channels.conversations || []).map((r) => [r.channel, r.c]));
    const custs = Object.fromEntries((data.channels.customers || []).map((r) => [r.channel, r.c]));
    $("an-channels").innerHTML = `<table class="rec-table">
      <thead><tr><th>Канал</th><th>Клиенты</th><th>Диалоги</th><th>Сообщения за период</th></tr></thead>
      <tbody>${(data.channels.messages || []).map((r) => `
        <tr><td>${channelPill(r.channel)}</td><td>${esc(custs[r.channel] || 0)}</td>
        <td>${esc(convs[r.channel] || 0)}</td><td>${esc(r.messages)}</td></tr>`).join("")}</tbody></table>`;
    const totalLeads = (data.leads.by_status || []).reduce((sum, r) => sum + r.c, 0) || 1;
    $("an-leads").innerHTML = (data.leads.by_status || []).map((r) => `
      <p>${esc(LEAD_LABELS[r.lead_status] || r.lead_status)}: <b>${esc(r.c)}</b>
      <span class="muted">(${Math.round((r.c / totalLeads) * 100)}%)</span></p>`).join("");
  } catch (err) {
    toast(err.message);
  }
}

$("analytics-days").addEventListener("change", loadAnalytics);

/* --- база знаний ------------------------------------------------------------ */

async function loadKb() {
  try {
    const data = await api("/admin/api/kb");
    $("kb-list").innerHTML = (data.items || []).length ? data.items.map((doc) => `
      <div class="insight">
        <div><b>${esc(doc.title || "Без заголовка")}</b> <span class="pill">${esc(doc.category)}</span>
          ${doc.enabled ? "" : `<span class="pill pill--paused">выключен</span>`}</div>
        <div class="muted">${esc(doc.text.slice(0, 200))}${doc.text.length > 200 ? "…" : ""}</div>
        <div style="margin-top:6px">
          <button class="btn btn--sm btn--ghost" data-kb-edit="${doc.id}">Править</button>
          <button class="btn btn--sm btn--ghost" data-kb-toggle="${doc.id}" data-enabled="${doc.enabled}">
            ${doc.enabled ? "Выключить" : "Включить"}</button>
        </div>
      </div>`).join("") : `<div class="empty">Документов в БД пока нет — работает база с сайта (yaml).</div>`;
  } catch (err) {
    toast(err.message);
  }
}

function kbForm(doc = {}) {
  $("drawer").hidden = false;
  $("drawer-title").textContent = doc.id ? "Документ базы знаний" : "Новый документ";
  $("drawer-body").innerHTML = `
    <label class="field"><span>Заголовок</span><input id="kb-title" value="${esc(doc.title || "")}" /></label>
    <label class="field" style="margin-top:10px"><span>Текст (факты, на которые бот может отвечать)</span>
      <textarea id="kb-text" rows="8">${esc(doc.text || "")}</textarea></label>
    <label class="field" style="margin-top:10px"><span>Категория</span>
      <input id="kb-category" value="${esc(doc.category || "custom")}" /></label>
    <div class="actions" style="margin-top:12px">
      <button class="btn" id="kb-save">${doc.id ? "Сохранить" : "Добавить"}</button>
    </div>`;
  $("kb-save").addEventListener("click", async () => {
    const payload = {
      title: $("kb-title").value.trim(),
      text: $("kb-text").value.trim(),
      category: $("kb-category").value.trim() || "custom",
    };
    if (!payload.text) { toast("Текст обязателен"); return; }
    try {
      if (doc.id) {
        await api(`/admin/api/kb/${doc.id}`, { method: "PATCH", body: JSON.stringify(payload) });
      } else {
        await api("/admin/api/kb", { method: "POST", body: JSON.stringify(payload) });
      }
      closeDrawer();
      toast("Сохранено. В поиске — в течение минуты.");
      loadKb();
    } catch (err) {
      toast(err.message);
    }
  });
}

$("kb-add").addEventListener("click", () => kbForm());

$("kb-list").addEventListener("click", async (event) => {
  const toggle = event.target.closest("[data-kb-toggle]");
  if (toggle) {
    await api(`/admin/api/kb/${toggle.dataset.kbToggle}`, {
      method: "PATCH",
      body: JSON.stringify({ enabled: toggle.dataset.enabled === "1" ? 0 : 1 }),
    }).catch((err) => toast(err.message));
    loadKb();
    return;
  }
  const edit = event.target.closest("[data-kb-edit]");
  if (edit) {
    const data = await api("/admin/api/kb");
    const doc = (data.items || []).find((d) => d.id === Number(edit.dataset.kbEdit));
    if (doc) kbForm(doc);
  }
});

/* Кнопка «в базу знаний» из раздела «Вопросы». */
$("insights").addEventListener("click", (event) => {
  const btn = event.target.closest("[data-kb-add]");
  if (btn) kbForm({ title: btn.dataset.kbAdd, text: "" });
});

/* --- AI: промпты и качество -------------------------------------------------- */

async function loadAiSection() {
  try {
    const [versions, events] = await Promise.all([
      api("/admin/api/ai/prompts"),
      api(`/admin/api/ai/events?days=${$("aiq-days").value}&kind=${$("aiq-kind").value}`),
    ]);
    renderPromptVersions(versions.items || []);
    renderAiEvents(events.items || []);
  } catch (err) {
    toast(err.message);
  }
}

async function renderPromptVersions(items) {
  const active = items.find((p) => p.active);
  if (active) {
    const full = await api(`/admin/api/ai/prompts/${active.id}`);
    $("ai-prompt-view").innerHTML = `
      <p class="muted">Активна версия <b>${esc(active.version)}</b>
      (${esc(full.chars || full.content.length)} символов, обновлена ${esc(fmtTime(active.created_at))})</p>
      <div class="preview-box" style="white-space:pre-wrap;max-height:220px;overflow:auto">${esc(full.content)}</div>`;
  } else {
    $("ai-prompt-view").innerHTML = `<p class="muted">Версий нет — работает промпт из кода.</p>`;
  }
  $("ai-prompt-versions").innerHTML = items.map((p) => `
    <div class="insight">
      <b>v${esc(p.version)}</b> ${p.active ? `<span class="pill pill--ai">активна</span>` : ""}
      <div class="muted">${esc(p.preview)}…</div>
      <div style="margin-top:6px">
        ${p.active ? "" : `<button class="btn btn--sm btn--ghost" data-activate="${p.id}">Активировать</button>`}
        <button class="btn btn--sm btn--ghost" data-view-prompt="${p.id}">Смотреть</button>
      </div>
    </div>`).join("") || `<div class="empty">Нет версий</div>`;
}

$("ai-prompt-versions").addEventListener("click", async (event) => {
  const activate = event.target.closest("[data-activate]");
  if (activate) {
    if (!confirm("Активировать эту версию? Она начнёт влиять на все ответы бота.")) return;
    try {
      await api(`/admin/api/ai/prompts/${activate.dataset.activate}/activate`, { method: "POST", body: "{}" });
      toast("Версия активирована");
      loadAiSection();
    } catch (err) {
      toast(err.message);
    }
    return;
  }
  const view = event.target.closest("[data-view-prompt]");
  if (view) {
    const full = await api(`/admin/api/ai/prompts/${view.dataset.viewPrompt}`);
    openDrawer(`Промпт v${full.version}`, async () => {
      $("drawer-body").innerHTML = `<div style="white-space:pre-wrap">${esc(full.content)}</div>`;
    });
  }
});

$("ai-prompt-save").addEventListener("click", async () => {
  const content = $("ai-prompt-new").value.trim();
  if (!content) { toast("Введите текст промпта"); return; }
  try {
    const created = await api("/admin/api/ai/prompts", {
      method: "POST", body: JSON.stringify({ content }),
    });
    await api(`/admin/api/ai/prompts/${created.id}/activate`, { method: "POST", body: "{}" });
    $("ai-prompt-new").value = "";
    toast("Новая версия сохранена и активирована");
    loadAiSection();
  } catch (err) {
    toast(err.message);
  }
});

function renderAiEvents(items) {
  $("aiq-list").innerHTML = items.length ? items.map((e) => {
    let detail = {};
    try { detail = JSON.parse(e.detail_json || "{}"); } catch (_) { /* игнор */ }
    return `<div class="ai-event">
      <span class="pill pill--paused">${esc(e.kind)}</span>
      <span class="muted"> ${esc(fmtTime(e.created_at))}</span>
      <div>${esc(detail.question || detail.text || detail.reason || "")}</div>
    </div>`;
  }).join("") : `<div class="empty">Событий нет — AI работает ровно.</div>`;
}

$("aiq-kind").addEventListener("change", loadAiSection);
$("aiq-days").addEventListener("change", loadAiSection);

/* --- центр ошибок ------------------------------------------------------------- */

const ERROR_CATEGORIES = {
  ai: "AI", channel: "Канал", ingestion: "Ingestion", broadcast: "Рассылка",
};

async function loadErrors() {
  try {
    const data = await api(
      `/admin/api/errors?days=${$("errors-days").value}&category=${$("errors-category").value}`);
    const items = data.items || [];
    $("nav-errors").hidden = !items.length;
    $("nav-errors").textContent = items.length || "";
    $("errors-list").innerHTML = items.length ? items.map((e) => `
      <div class="ai-event">
        <span class="pill pill--paused">${esc(ERROR_CATEGORIES[e.category] || e.category)}</span>
        <span class="pill">${esc(e.kind)}</span>
        <span class="muted"> ${esc(fmtTime(e.ts))}${e.channel ? " · " + esc(CHANNEL_LABEL[e.channel] || e.channel) : ""}</span>
        <div>${esc((e.detail && (e.detail.error || e.detail.question || e.detail.text || e.detail.reason)) || "")}</div>
        ${e.category === "broadcast" ? `<button class="btn btn--sm btn--ghost" data-err-retry="${e.id}" data-broadcast="${e.broadcast_id}">Повторить отправку</button>` : ""}
      </div>`).join("") : `<div class="empty">Ошибок за период нет.</div>`;
  } catch (err) {
    toast(err.message);
  }
}

$("errors-category").addEventListener("change", loadErrors);
$("errors-days").addEventListener("change", loadErrors);

$("errors-list").addEventListener("click", async (event) => {
  const retry = event.target.closest("[data-err-retry]");
  if (!retry) return;
  retry.disabled = true;
  try {
    const result = await api(
      `/admin/api/broadcasts/${retry.dataset.broadcast}/recipients/${retry.dataset.errRetry}/retry`,
      { method: "POST", body: "{}" });
    toast(result.ok ? "Переотправлено" : `Снова ошибка: ${result.error || ""}`);
  } catch (err) {
    toast(err.message);
  }
  loadErrors();
});

/* --- пользователи админки (super_admin) -------------------------------------- */

const ROLE_TITLES = {
  super_admin: "super_admin (всё)",
  admin: "admin (всё, кроме пользователей и промптов)",
  manager: "manager (диалоги и клиенты)",
  marketing: "marketing (рассылки и аналитика)",
  support: "support (минимум)",
};

async function loadAdminUsers() {
  try {
    const data = await api("/admin/api/admin-users");
    $("au-list").innerHTML = (data.items || []).map((u) => `
      <div class="insight">
        <b>${esc(u.username)}</b> <span class="pill">${esc(u.role)}</span>
        ${u.active ? "" : `<span class="pill pill--paused">выключен</span>`}
        <div class="muted">создан ${esc(fmtTime(u.created_at))}${u.last_login_at ? ` · входил ${esc(fmtTime(u.last_login_at))}` : ""}</div>
        <div style="margin-top:6px" class="builder-row">
          <select data-au-role="${u.id}">
            ${Object.keys(ROLE_TITLES).map((r) =>
              `<option value="${r}" ${u.role === r ? "selected" : ""}>${esc(ROLE_TITLES[r])}</option>`).join("")}
          </select>
          <input data-au-pass="${u.id}" type="password" placeholder="Новый пароль" style="max-width:160px" />
          <button class="btn btn--sm btn--ghost" data-au-save="${u.id}">Сохранить</button>
          <button class="btn btn--sm btn--ghost" data-au-toggle="${u.id}" data-active="${u.active}">
            ${u.active ? "Выключить" : "Включить"}</button>
        </div>
      </div>`).join("") || `<div class="empty">Пользователей нет</div>`;
  } catch (err) {
    toast(err.message);
  }
}

$("au-add").addEventListener("click", async () => {
  const username = $("au-username").value.trim();
  const password = $("au-password").value;
  const role = $("au-role").value;
  if (!username || password.length < 6) {
    toast("Логин и пароль (мин. 6 символов) обязательны");
    return;
  }
  try {
    await api("/admin/api/admin-users", {
      method: "POST",
      body: JSON.stringify({ username, password, role }),
    });
    $("au-username").value = "";
    $("au-password").value = "";
    toast("Пользователь создан");
    loadAdminUsers();
  } catch (err) {
    toast(err.message);
  }
});

$("au-list").addEventListener("click", async (event) => {
  const save = event.target.closest("[data-au-save]");
  if (save) {
    const id = save.dataset.auSave;
    const role = document.querySelector(`[data-au-role="${id}"]`).value;
    const password = document.querySelector(`[data-au-pass="${id}"]`).value;
    const body = { role };
    if (password) body.password = password;
    try {
      await api(`/admin/api/admin-users/${id}`, { method: "PATCH", body: JSON.stringify(body) });
      toast("Сохранено");
      loadAdminUsers();
    } catch (err) {
      toast(err.message);
    }
    return;
  }
  const toggle = event.target.closest("[data-au-toggle]");
  if (toggle) {
    try {
      await api(`/admin/api/admin-users/${toggle.dataset.auToggle}`, {
        method: "PATCH",
        body: JSON.stringify({ active: toggle.dataset.active === "1" ? 0 : 1 }),
      });
      loadAdminUsers();
    } catch (err) {
      toast(err.message);
    }
  }
});

/* --- старт ------------------------------------------------------------------ */

(async function init() {
  if (!TOKEN) {
    showGate("");
    return;
  }
  try {
    await enter(TOKEN);
  } catch (err) {
    showGate(err.message === "unauthorized" ? "Токен больше не подходит" : err.message);
  }
})();
