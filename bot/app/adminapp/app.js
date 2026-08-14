/* Админка бота: клиенты, переписка, заявки, рассылки.
 *
 * Токен живёт только в localStorage этого браузера и уходит исключительно
 * заголовком X-Admin-Token — в URL его класть нельзя, он осядет в логах
 * прокси и в истории браузера.
 */
const TOKEN_KEY = "foxinburg-admin-token";
const REQUEST_TIMEOUT_MS = 20000;

let TOKEN = localStorage.getItem(TOKEN_KEY) || "";
let USERS = [];
let SELECTED = "";

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
    if (resp.status === 401) {
      throw new Error("unauthorized");
    }
    if (!resp.ok) {
      throw new Error(`Сервер ответил ${resp.status}`);
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

/* --- вход ----------------------------------------------------------------- */

function showGate(message) {
  $("gate").hidden = false;
  $("app").hidden = true;
  const error = $("gate-error");
  error.hidden = !message;
  error.textContent = message || "";
}

async function enter(token) {
  TOKEN = token;
  await api("/admin/broadcast/audience"); // самая дешёвая ручка — проверка токена
  localStorage.setItem(TOKEN_KEY, token);
  $("gate").hidden = true;
  $("app").hidden = false;
  await loadAll();
}

$("gate-form").addEventListener("submit", async (event) => {
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
  localStorage.removeItem(TOKEN_KEY);
  TOKEN = "";
  $("gate-token").value = "";
  showGate("");
});

$("refresh").addEventListener("click", () => loadAll());

/* --- вкладки -------------------------------------------------------------- */

$("tabs").addEventListener("click", (event) => {
  const tab = event.target.closest(".tab");
  if (!tab) return;
  document.querySelectorAll(".tab").forEach((el) => el.classList.toggle("tab--active", el === tab));
  ["clients", "leads", "broadcast", "insights"].forEach((name) => {
    $(`panel-${name}`).hidden = name !== tab.dataset.tab;
  });
});

/* --- данные --------------------------------------------------------------- */

async function loadAll() {
  try {
    const [users, audience] = await Promise.all([
      api("/admin/users"),
      api("/admin/broadcast/audience"),
    ]);
    USERS = users.rows || [];
    renderClients();
    renderLeads();
    renderAudience(audience);
    loadInsights();
  } catch (err) {
    if (err.message === "unauthorized") {
      showGate("Токен больше не подходит");
      return;
    }
    toast(err.message);
  }
}

async function loadInsights() {
  try {
    const data = await api("/admin/insights?days=30");
    const items = data.top_questions || data.rows || [];
    $("insights").innerHTML = items.length
      ? items.map((item) => `
          <div class="insight">
            <div>${esc(item.question || item.text || "")}</div>
            <div class="muted">${esc(item.count ? `${item.count} раз` : "")} ${esc(item.at || "")}</div>
          </div>`).join("")
      : `<div class="empty">За 30 дней бот не спасовал ни разу.</div>`;
  } catch (err) {
    $("insights").innerHTML = `<div class="empty">${esc(err.message)}</div>`;
  }
}

/* --- клиенты и заявки ----------------------------------------------------- */

function personName(row) {
  const parts = [row.fio_parent, row.fio_child].filter(Boolean);
  if (parts.length === 2) return `${row.fio_parent} · ребёнок ${row.fio_child}`;
  return parts[0] || row.user_id;
}

function statusPill(row) {
  // Значения приходят из broadcast._lead_status: complete / partial / none.
  if (row.lead_status === "complete") return `<span class="pill pill--lead">заявка</span>`;
  if (row.lead_status === "partial") return `<span class="pill pill--partial">не дошёл</span>`;
  return "";
}

function platformPill(row) {
  const isTelegram = row.platform === "telegram" || String(row.user_id).startsWith("tg:");
  return `<span class="pill ${isTelegram ? "pill--tg" : ""}">${isTelegram ? "Telegram" : "MAX"}</span>`;
}

function rowHtml(row) {
  const when = row.updated_at ? row.updated_at.slice(0, 16).replace("T", " ") : "";
  return `
    <button class="row ${row.user_id === SELECTED ? "row--active" : ""}" data-user="${esc(row.user_id)}">
      <span class="row__top">
        <span class="row__name">${esc(personName(row))}</span>
        ${platformPill(row)} ${statusPill(row)}
      </span>
      <span class="row__meta">${esc(row.phone || "телефона нет")} · ${esc(row.msg_count)} сообщ. · ${esc(when)}</span>
      <span class="row__last">${esc(row.last_message || "")}</span>
    </button>`;
}

function renderClients() {
  const needle = $("search").value.trim().toLowerCase();
  const rows = USERS.filter((row) => {
    if (!needle) return true;
    return [row.fio_parent, row.fio_child, row.phone, row.first_question, row.user_id]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(needle));
  });
  $("count-clients").textContent = USERS.length ? USERS.length : "";
  $("clients-list").innerHTML = rows.length
    ? rows.map(rowHtml).join("")
    : `<div class="empty">Никого не нашлось</div>`;
}

function renderLeads() {
  const rows = USERS.filter((row) => row.lead_status && row.lead_status !== "none");
  $("count-leads").textContent = rows.length ? rows.length : "";
  $("leads-list").innerHTML = rows.length
    ? rows.map(rowHtml).join("")
    : `<div class="empty">Заявок пока нет</div>`;
}

$("search").addEventListener("input", renderClients);

document.addEventListener("click", async (event) => {
  const row = event.target.closest(".row");
  if (!row) return;
  SELECTED = row.dataset.user;
  renderClients();
  renderLeads();
  const target = row.closest("#leads-list") ? $("detail-leads") : $("detail");
  target.innerHTML = `<div class="detail__empty">Загружаю…</div>`;
  try {
    const data = await api(`/admin/users/${encodeURIComponent(SELECTED)}`);
    target.innerHTML = detailHtml(data);
  } catch (err) {
    target.innerHTML = `<div class="detail__empty">${esc(err.message)}</div>`;
  }
});

const FACT_LABELS = {
  fio_parent: "Родитель",
  fio_child: "Ребёнок",
  phone: "Телефон",
  birthday: "Дата рождения",
  age: "Возраст",
  course: "Курс",
  branch: "Филиал",
  email: "E-mail",
  city: "Город",
  comment: "Комментарий",
};

function detailHtml(data) {
  const header = data.header || {};
  const lead = header.lead || {};
  const facts = Object.keys(FACT_LABELS)
    .filter((key) => lead[key])
    .map((key) => `<div><dt>${esc(FACT_LABELS[key])}</dt><dd>${esc(lead[key])}</dd></div>`)
    .join("");
  // Без отступов и переносов внутри .msg: у него white-space: pre-wrap,
  // и любой пробел из шаблона превратился бы в пустоту на экране.
  const transcript = (data.transcript || [])
    .map((msg) =>
      `<div class="msg msg--${msg.role === "user" ? "user" : "assistant"}">` +
      `<span class="msg__who">${msg.role === "user" ? "Клиент" : "Бот"}</span>` +
      `${esc(msg.content || msg.text || "")}</div>`)
    .join("");
  return `
    <h2>${esc(personName({ ...lead, user_id: header.user_id }))}</h2>
    <div class="muted">${esc(header.user_id)} · этап ${esc(header.stage || "—")}</div>
    <dl class="facts">${facts || `<div><dt>Данных нет</dt><dd>—</dd></div>`}</dl>
    <div class="transcript">${transcript || `<div class="muted">Переписки нет</div>`}</div>`;
}

/* --- рассылка ------------------------------------------------------------- */

function renderAudience(data) {
  const segments = data.segments || {};
  $("audience").innerHTML = `
    <span>Всего: <b>${esc(data.total ?? 0)}</b></span>
    <span>С заявкой: <b>${esc(segments.leads ?? 0)}</b></span>`;
}

async function broadcast(kind) {
  const text = $("bc-text").value.trim();
  if (!text) {
    toast("Сначала напишите текст");
    return;
  }
  const isTest = kind === "test";
  if (!isTest) {
    const segment = $("bc-segment").value;
    const count = segment === "leads" ? $("count-leads").textContent || "0" : USERS.length;
    if (!confirm(`Отправить сообщение ${count} клиентам? Отменить будет нельзя.`)) return;
  }
  const button = isTest ? $("bc-test") : $("bc-send");
  button.disabled = true;
  try {
    const body = isTest
      ? { text }
      : { text, segment: $("bc-segment").value };
    const result = await api(isTest ? "/admin/broadcast/test" : "/admin/broadcast/send", {
      method: "POST",
      body: JSON.stringify(body),
    });
    const box = $("bc-result");
    box.hidden = false;
    box.textContent = `Отправлено: ${result.sent ?? 0}, не доставлено: ${result.failed ?? 0}`;
    toast(isTest ? "Отправлено вам" : "Рассылка ушла");
  } catch (err) {
    toast(err.message);
  } finally {
    button.disabled = false;
  }
}

$("bc-test").addEventListener("click", () => broadcast("test"));
$("bc-send").addEventListener("click", () => broadcast("send"));

/* --- старт ---------------------------------------------------------------- */

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
