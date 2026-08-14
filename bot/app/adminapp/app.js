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
  ["clients", "leads", "broadcast", "insights", "schedule"].forEach((name) => {
    $(`panel-${name}`).hidden = name !== tab.dataset.tab;
  });
  if (tab.dataset.tab === "schedule") loadImportStatus();
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

/* --- импорт расписания ------------------------------------------------------
 *
 * Три шага: файл → сопоставление колонок (запоминается) → отчёт. Файл не
 * хранится на сервере; несопоставленные строки не теряются — их можно
 * привязать к клиенту вручную. */

const IMPORT_FIELDS = {
  student: "Имя ученика",
  phone: "Телефон родителя",
  weekday: "День недели",
  time: "Время",
  program: "Программа",
  teacher: "Педагог",
  filial: "Филиал",
};

let IMPORT_PREVIEW = null;

async function apiUpload(path, formData) {
  const resp = await fetch(path, {
    method: "POST",
    headers: { "X-Admin-Token": TOKEN }, // Content-Type ставит сам браузер (multipart boundary)
    body: formData,
  });
  if (resp.status === 401) throw new Error("unauthorized");
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(data.error || `Сервер ответил ${resp.status}`);
  return data;
}

async function loadImportStatus() {
  try {
    const data = await api("/admin/import/status");
    const box = $("import-status");
    if (!data.batch) {
      box.innerHTML = `<div class="empty">Расписание ещё ни разу не загружали. В кабинете учеников вместо занятий — честная заглушка и кнопка «Спросить расписание».</div>`;
    } else {
      const age = data.age_days != null ? Math.floor(data.age_days) : "?";
      box.innerHTML = `
        <div class="import-batch">
          <b>Последняя загрузка:</b> ${esc(data.batch.uploaded_at.slice(0, 16).replace("T", " "))}
          (${age} дн. назад${data.needs_import ? " — пора загрузить свежую" : ""})<br>
          Строк: ${esc(data.batch.rows_total)}, сопоставлено: ${esc(data.batch.rows_matched)},
          не сопоставлено: ${esc(data.batch.rows_unmatched)}
        </div>`;
    }
    renderUnmatched(data);
  } catch (err) {
    toast(err.message);
  }
}

function renderUnmatched(data) {
  const box = $("import-unmatched");
  const rows = data.unmatched || [];
  if (!rows.length) {
    box.innerHTML = "";
    return;
  }
  box.innerHTML = `
    <h3>Не сопоставлено: ${rows.length}</h3>
    <p class="hint">Этих учеников бот не нашёл по телефону и имени. Выберите клиента — расписание появится у него в кабинете.</p>
    ${rows.map((row) => `
      <div class="unmatched">
        <div><b>${esc(row.student)}</b> — ${esc(row.weekday)} ${esc(row.time)} ${esc(row.program || "")}</div>
        <select data-unmatched-row="${esc(row.row_index)}">
          <option value="">Выбрать клиента…</option>
          ${USERS.map((u) => `
            <option value="${esc(u.platform)}|${esc(u.user_id)}">
              ${esc(personName(u))} ${esc(u.phone || "")}
            </option>`).join("")}
        </select>
      </div>`).join("")}`;
  box.querySelectorAll("select[data-unmatched-row]").forEach((sel) => {
    sel.addEventListener("change", async () => {
      if (!sel.value) return;
      const [platform, user_id] = sel.value.split("|");
      try {
        await api("/admin/import/match", {
          method: "POST",
          body: JSON.stringify({
            batch_id: data.batch.id,
            row_index: Number(sel.dataset.unmatchedRow),
            platform,
            user_id,
          }),
        });
        toast("Сопоставлено");
        loadImportStatus();
      } catch (err) {
        toast(err.message);
      }
    });
  });
}

$("import-file").addEventListener("change", async () => {
  const file = $("import-file").files[0];
  if (!file) return;
  const formData = new FormData();
  formData.append("file", file);
  try {
    const data = await apiUpload("/admin/import/preview", formData);
    IMPORT_PREVIEW = data;
    renderMapping(data);
  } catch (err) {
    toast(err.message);
  }
});

function renderMapping(data) {
  const box = $("import-mapping");
  box.hidden = false;
  box.innerHTML = `
    <h3>Колонки файла (${esc(data.rows_count)} строк)</h3>
    ${Object.keys(IMPORT_FIELDS).map((field) => `
      <label class="field">
        <span>${esc(IMPORT_FIELDS[field])}${field === "student" ? " *" : ""}</span>
        <select data-map-field="${esc(field)}">
          <option value="">— нет в файле —</option>
          ${data.headers.map((h) => `
            <option value="${esc(h)}"${data.mapping[field] === h ? " selected" : ""}>${esc(h)}</option>`).join("")}
        </select>
      </label>`).join("")}
    <details class="hint"><summary>Первые строки файла</summary>
      <pre>${esc(JSON.stringify(data.sample, null, 2))}</pre>
    </details>`;
  $("import-commit").hidden = false;
}

$("import-commit").addEventListener("click", async () => {
  const file = $("import-file").files[0];
  if (!file || !IMPORT_PREVIEW) return;
  const mapping = {};
  document.querySelectorAll("[data-map-field]").forEach((sel) => {
    if (sel.value) mapping[sel.dataset.mapField] = sel.value;
  });
  if (!mapping.student) {
    toast("Выберите колонку с именем ученика");
    return;
  }
  const formData = new FormData();
  formData.append("file", file);
  formData.append("mapping", JSON.stringify(mapping));
  const button = $("import-commit");
  button.disabled = true;
  try {
    const data = await apiUpload("/admin/import/commit", formData);
    const report = data.report || {};
    const box = $("import-report");
    box.hidden = false;
    box.innerHTML = `
      <b>Отчёт об импорте</b><br>
      Строк в файле: ${esc(report.rows_total ?? 0)}<br>
      Сопоставлено с клиентами: ${esc(report.rows_matched ?? 0)}<br>
      Не сопоставлено: ${esc(report.rows_unmatched ?? 0)}<br>
      Расписание изменилось у клиентов: ${esc(report.changed_users ?? 0)}`;
    toast("Расписание загружено");
    $("import-mapping").hidden = true;
    button.hidden = true;
    loadImportStatus();
  } catch (err) {
    toast(err.message);
  } finally {
    button.disabled = false;
  }
});
