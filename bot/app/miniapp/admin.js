const API = "";
const STORAGE_KEY = "foxinburg_admin_token";

const STAGE_OPTIONS = [
  ["all", "все"],
  ["greeting", "приветствие"],
  ["discovery", "выявление"],
  ["selection", "подбор"],
  ["objection", "возражения"],
  ["lead", "заявка"],
  ["done", "готово"],
  ["handoff", "админ"],
];

const STAGE_LABELS = Object.fromEntries(STAGE_OPTIONS.slice(1));
const LEAD_LABELS = {
  complete: "оставил",
  partial: "начал",
  none: "—",
};

let audience = null;
let usersRows = [];
let usersDetail = null;
let activeTab = "broadcast";

const els = {};

function qs(id) {
  return document.getElementById(id);
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function escapeCsv(value) {
  return `"${String(value ?? "").replace(/"/g, '""').replace(/\r?\n/g, " ")}"`;
}

function getToken() {
  return localStorage.getItem(STORAGE_KEY) || "";
}

function setToken(token) {
  const trimmed = (token || "").trim();
  if (trimmed) localStorage.setItem(STORAGE_KEY, trimmed);
  else localStorage.removeItem(STORAGE_KEY);
  return trimmed;
}

function showError(message) {
  els.authError.style.display = "block";
  els.authError.textContent = message;
}

function clearError() {
  els.authError.style.display = "none";
  els.authError.textContent = "";
}

function showOk(message) {
  els.authOk.style.display = "block";
  els.authOk.textContent = message;
}

function clearOk() {
  els.authOk.style.display = "none";
  els.authOk.textContent = "";
}

function showResult(message, isError = false) {
  els.result.classList.toggle("ok", !isError);
  els.result.classList.toggle("error", isError);
  els.result.style.display = "block";
  els.result.textContent = message;
}

function authHeaders() {
  return {
    "Content-Type": "application/json",
    "X-Admin-Token": getToken(),
  };
}

async function requestJSON(url, options = {}) {
  const resp = await fetch(API + url, {
    ...options,
    headers: {
      ...authHeaders(),
      ...(options.headers || {}),
    },
  });
  let data = null;
  try {
    data = await resp.json();
  } catch {
    data = null;
  }
  if (resp.status === 401) {
    throw new Error("401");
  }
  if (!resp.ok) {
    const detail = data && (data.detail || data.error) ? (data.detail || data.error) : `${resp.status}`;
    throw new Error(detail);
  }
  return data;
}

function currentSegment() {
  const checked = document.querySelector('input[name="segment"]:checked');
  return checked ? checked.value : "all";
}

function courseCount(value) {
  const item = (audience?.courses || []).find(x => x.value === value);
  return item ? item.count : 0;
}

function branchCount(value) {
  const item = (audience?.branches || []).find(x => x.value === value);
  return item ? item.count : 0;
}

function updateSegmentVisibility() {
  const segment = currentSegment();
  els.courseWrap.style.display = segment === "course" ? "block" : "none";
  els.branchWrap.style.display = segment === "branch" ? "block" : "none";
}

function updatePreview() {
  const text = els.messageText.value.trim();
  const buttonText = els.buttonText.value.trim();
  const buttonUrl = els.buttonUrl.value.trim();
  const parts = [];
  parts.push(text || "Текст рассылки появится здесь.");
  if (buttonText && buttonUrl) {
    parts.push(`\nКнопка: ${buttonText} → ${buttonUrl}`);
  } else if (buttonText || buttonUrl) {
    parts.push("\nКнопка будет доступна после заполнения обоих полей.");
  }
  els.preview.innerHTML = escapeHtml(parts.join("\n"));
}

function updateCounts() {
  if (!audience) {
    els.recipientCount.textContent = "Получателей: 0";
    els.audienceSummary.innerHTML = "";
    return;
  }
  const segment = currentSegment();
  let count = 0;
  let extra = "";
  if (segment === "all") {
    count = audience.segments.all || 0;
    extra = "Все пользователи, которые писали боту.";
  } else if (segment === "leads") {
    count = audience.segments.leads || 0;
    extra = "Пользователи со завершённой заявкой.";
  } else if (segment === "course") {
    const value = els.courseSelect.value;
    count = value ? courseCount(value) : 0;
    extra = value ? `Курс: ${value}` : "Выберите курс.";
  } else if (segment === "branch") {
    const value = els.branchSelect.value;
    count = value ? branchCount(value) : 0;
    extra = value ? `Филиал: ${value}` : "Выберите филиал.";
  }
  els.recipientCount.textContent = `Получателей: ${count}`;
  els.audienceSummary.innerHTML = `
    <div><b>Всего диалогов:</b> ${audience.total || 0}</div>
    <div><b>Сегмент:</b> ${escapeHtml(segment)}</div>
    <div><b>Примечание:</b> ${escapeHtml(extra)}</div>
    <div style="margin-top:8px;" class="mini">Доступные курсы: ${(audience.courses || []).length}, филиалы: ${(audience.branches || []).length}</div>
  `;
}

function populateSelect(select, items, placeholder) {
  const options = [`<option value="">${escapeHtml(placeholder)}</option>`];
  for (const item of items || []) {
    options.push(`<option value="${escapeHtml(item.value)}">${escapeHtml(item.value)} (${item.count})</option>`);
  }
  select.innerHTML = options.join("");
}

function renderAudience() {
  if (!audience) return;
  populateSelect(els.courseSelect, audience.courses || [], "Выберите курс");
  populateSelect(els.branchSelect, audience.branches || [], "Выберите филиал");
  updateSegmentVisibility();
  updateCounts();
}

async function loadAudience() {
  const data = await requestJSON("/admin/broadcast/audience", { method: "GET" });
  audience = data;
  renderAudience();
}

function requiredTokenMessage() {
  return "Требуется административный токен.";
}

function requireToken() {
  const token = getToken();
  if (!token) {
    showError(requiredTokenMessage());
    return false;
  }
  clearError();
  return true;
}

async function ensureAudience() {
  if (!requireToken()) return;
  try {
    await loadAudience();
    els.loginCard.classList.add("hidden");
    els.appShell.classList.remove("hidden");
    showOk("Токен принят. Конструктор рассылки открыт.");
  } catch (err) {
    if (String(err.message) === "401") {
      setToken("");
      els.appShell.classList.add("hidden");
      els.loginCard.classList.remove("hidden");
      showError("Неверный или отсутствующий токен администратора.");
      return;
    }
    showError(`Не удалось загрузить аудиторию: ${err.message}`);
  }
}

function setActiveTab(tab) {
  activeTab = tab;
  closeUserModal();
  els.tabButtons.forEach(btn => {
    btn.classList.toggle("active", btn.dataset.tab === tab);
  });
  els.panelBroadcast.classList.toggle("hidden", tab !== "broadcast");
  els.panelUsers.classList.toggle("hidden", tab !== "users");
}

async function loadUsers() {
  const data = await requestJSON("/admin/users", { method: "GET" });
  usersRows = Array.isArray(data.rows) ? data.rows : [];
  populateStageFilter();
  renderUsers();
}

function populateStageFilter() {
  const current = els.userStageFilter.value || "all";
  const options = STAGE_OPTIONS.map(([value, label]) => `<option value="${value}">${escapeHtml(label)}</option>`);
  els.userStageFilter.innerHTML = options.join("");
  els.userStageFilter.value = STAGE_OPTIONS.some(([value]) => value === current) ? current : "all";
}

function formatDateRu(value) {
  if (!value) return "—";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return value;
  return new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(dt);
}

function stageLabel(value) {
  return STAGE_LABELS[value] || value || "—";
}

function leadLabel(value) {
  return LEAD_LABELS[value] || "—";
}

function rowInterest(row) {
  return [row.course, row.branch, row.format].filter(Boolean).join(" / ");
}

function filteredUsers() {
  const stage = els.userStageFilter.value || "all";
  const query = (els.userInterestFilter.value || "").trim().toLowerCase();
  return usersRows.filter(row => {
    if (stage !== "all" && row.stage !== stage) return false;
    if (query && !rowInterest(row).toLowerCase().includes(query)) return false;
    return true;
  });
}

function renderUsers() {
  const rows = filteredUsers();
  els.usersCount.textContent = `Всего: ${usersRows.length} / Показано: ${rows.length}`;
  if (!rows.length) {
    els.usersTableBody.innerHTML = `<tr><td colspan="8" class="muted">Пользователи не найдены.</td></tr>`;
    return;
  }
  els.usersTableBody.innerHTML = rows.map(row => `
    <tr data-user-id="${escapeHtml(row.user_id)}" title="Открыть переписку" tabindex="0" style="cursor:pointer;">
      <td>${escapeHtml(formatDateRu(row.first_at))}</td>
      <td>${escapeHtml(row.first_question || "—")}</td>
      <td>${escapeHtml(rowInterest(row) || "—")}</td>
      <td>${escapeHtml(stageLabel(row.stage))}</td>
      <td>${escapeHtml(leadLabel(row.lead_status))}</td>
      <td>${escapeHtml(String(row.msg_count ?? 0))}</td>
      <td>${escapeHtml(formatDateRu(row.updated_at))}</td>
      <td>${escapeHtml(row.source || "—")}</td>
    </tr>
  `).join("");
  els.usersTableBody.querySelectorAll("tr[data-user-id]").forEach(tr => {
    tr.addEventListener("click", () => openUserModal(tr.dataset.userId));
    tr.addEventListener("keypress", ev => {
      if (ev.key === "Enter" || ev.key === " ") {
        ev.preventDefault();
        openUserModal(tr.dataset.userId);
      }
    });
  });
}

function closeUserModal() {
  els.userModal.classList.add("hidden");
  usersDetail = null;
}

function downloadText(filename, content) {
  const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function downloadCsv(filename, rows) {
  const header = [
    "user_id",
    "first_at",
    "first_question",
    "interest",
    "stage",
    "lead_status",
    "msg_count",
    "updated_at",
    "source",
  ];
  const lines = [header.join(",")];
  for (const row of rows) {
    lines.push([
      row.user_id,
      row.first_at,
      row.first_question,
      rowInterest(row),
      row.stage,
      row.lead_status,
      row.msg_count,
      row.updated_at,
      row.source,
    ].map(escapeCsv).join(","));
  }
  downloadText(filename, lines.join("\n"));
}

function renderUserDetail(detail) {
  const header = detail.header || {};
  const transcript = Array.isArray(detail.transcript) ? detail.transcript : [];
  const lead = header.lead || {};
  const leadLines = Object.entries(lead).map(([key, value]) => `<div><b>${escapeHtml(key)}:</b> ${escapeHtml(value)}</div>`).join("");
  els.userModalTitle.textContent = `Переписка: ${header.user_id || "—"}`;
  els.userModalSubtitle.innerHTML = `
    <div><b>Этап:</b> ${escapeHtml(stageLabel(header.stage))} · <b>Заявка:</b> ${escapeHtml(leadLabel(header.lead_status))}</div>
    <div><b>Интерес:</b> ${escapeHtml([header.course, header.branch, header.format].filter(Boolean).join(" / ") || "—")}</div>
    <div><b>Создан:</b> ${escapeHtml(formatDateRu(header.created_at))} · <b>Активность:</b> ${escapeHtml(formatDateRu(header.updated_at))}</div>
    ${leadLines ? `<div style="margin-top:6px;display:grid;gap:4px;">${leadLines}</div>` : ""}
  `;
  if (!transcript.length) {
    els.userModalBody.innerHTML = '<div class="muted">Переписка пуста.</div>';
    return;
  }
  els.userModalBody.innerHTML = transcript.map(item => `
    <div class="card" style="background:#fcfbff;">
      <div class="split" style="margin-bottom:6px;">
        <b>${escapeHtml(item.role === "user" ? "Клиент" : item.role === "assistant" ? "Бот" : item.role || "")}</b>
        <span class="mini">${escapeHtml(formatDateRu(item.ts))}</span>
      </div>
      <div style="white-space:pre-wrap;line-height:1.55;">${escapeHtml(item.content || "")}</div>
    </div>
  `).join("");
}

async function openUserModal(userId) {
  try {
    const detail = await requestJSON(`/admin/users/${encodeURIComponent(userId)}`, { method: "GET" });
    usersDetail = detail;
    renderUserDetail(detail);
    els.userModal.classList.remove("hidden");
  } catch (err) {
    if (String(err.message) === "401") {
      setToken("");
      els.loginCard.classList.remove("hidden");
      els.appShell.classList.add("hidden");
      showError("Сессия администратора истекла или токен неверный.");
      return;
    }
    showError(`Не удалось загрузить переписку: ${err.message}`);
  }
}

function transcriptText(detail) {
  const header = detail.header || {};
  const transcript = Array.isArray(detail.transcript) ? detail.transcript : [];
  const lines = [
    `Пользователь: ${header.user_id || ""}`,
    `Этап: ${header.stage || ""}`,
    `Интерес: ${[header.course, header.branch, header.format].filter(Boolean).join(" / ")}`,
    `Заявка: ${header.lead_status || ""}`,
    `Создан: ${header.created_at || ""}`,
    `Активность: ${header.updated_at || ""}`,
    "",
  ];
  for (const item of transcript) {
    const who = item.role === "user" ? "Клиент" : item.role === "assistant" ? "Бот" : item.role || "";
    lines.push(`[${item.ts || ""}] ${who}: ${item.content || ""}`);
  }
  return lines.join("\n");
}

function exportUsersCsv() {
  downloadCsv(`users-${new Date().toISOString().slice(0, 10)}.csv`, filteredUsers());
}

function bindEvents() {
  els.tokenSave.addEventListener("click", async () => {
    const token = setToken(els.tokenInput.value);
    if (!token) {
      showError("Введите токен.");
      return;
    }
    await ensureAudience();
  });

  els.changeToken.addEventListener("click", () => {
    const token = setToken(window.prompt("Введите новый X-Admin-Token:", getToken()) || "");
    if (!token) {
      showError("Токен не сохранён.");
      return;
    }
    els.tokenInput.value = token;
    ensureAudience();
  });

  els.messageText.addEventListener("input", updatePreview);
  els.buttonText.addEventListener("input", updatePreview);
  els.buttonUrl.addEventListener("input", updatePreview);

  els.segmentBox.addEventListener("change", () => {
    updateSegmentVisibility();
    updateCounts();
  });
  els.courseSelect.addEventListener("change", updateCounts);
  els.branchSelect.addEventListener("change", updateCounts);

  els.sendTest.addEventListener("click", () => sendBroadcast(true));
  els.sendBroadcast.addEventListener("click", () => sendBroadcast(false));

  els.tabButtons.forEach(btn => {
    btn.addEventListener("click", async () => {
      const tab = btn.dataset.tab;
      setActiveTab(tab);
      if (tab === "users") {
        try {
          await loadUsers();
        } catch (err) {
          if (String(err.message) === "401") {
            setToken("");
            els.loginCard.classList.remove("hidden");
            els.appShell.classList.add("hidden");
            showError("Сессия администратора истекла или токен неверный.");
            return;
          }
          showError(`Не удалось загрузить пользователей: ${err.message}`);
        }
      }
    });
  });

  els.usersRefresh.addEventListener("click", async () => {
    try {
      await loadUsers();
    } catch (err) {
      if (String(err.message) === "401") {
        setToken("");
        els.loginCard.classList.remove("hidden");
        els.appShell.classList.add("hidden");
        showError("Сессия администратора истекла или токен неверный.");
        return;
      }
      showError(`Не удалось загрузить пользователей: ${err.message}`);
    }
  });

  els.userStageFilter.addEventListener("change", renderUsers);
  els.userInterestFilter.addEventListener("input", renderUsers);
  els.usersExport.addEventListener("click", exportUsersCsv);

  els.userClose.addEventListener("click", closeUserModal);
  els.userModal.addEventListener("click", ev => {
    if (ev.target === els.userModal) closeUserModal();
  });
  els.userDownload.addEventListener("click", () => {
    if (!usersDetail) return;
    const name = `conversation-${usersDetail.header?.user_id || "user"}.txt`;
    downloadText(name, transcriptText(usersDetail));
  });

  document.addEventListener("keydown", ev => {
    if (ev.key === "Escape" && !els.userModal.classList.contains("hidden")) {
      closeUserModal();
    }
  });
}

function init() {
  els.authError = qs("auth-error");
  els.authOk = qs("auth-ok");
  els.loginCard = qs("login-card");
  els.appShell = qs("app-shell");
  els.tokenInput = qs("token-input");
  els.tokenSave = qs("token-save");
  els.changeToken = qs("change-token");
  els.messageText = qs("message-text");
  els.buttonText = qs("button-text");
  els.buttonUrl = qs("button-url");
  els.preview = qs("preview");
  els.recipientCount = qs("recipient-count");
  els.audienceSummary = qs("audience-summary");
  els.segmentBox = qs("segment-box");
  els.courseWrap = qs("course-wrap");
  els.branchWrap = qs("branch-wrap");
  els.courseSelect = qs("course-select");
  els.branchSelect = qs("branch-select");
  els.sendTest = qs("send-test");
  els.sendBroadcast = qs("send-broadcast");
  els.tabButtons = Array.from(document.querySelectorAll(".tab[data-tab]"));
  els.panelBroadcast = qs("panel-broadcast");
  els.panelUsers = qs("panel-users");
  els.usersRefresh = qs("users-refresh");
  els.usersExport = qs("users-export");
  els.userStageFilter = qs("user-stage-filter");
  els.userInterestFilter = qs("user-interest-filter");
  els.usersCount = qs("users-count");
  els.usersTableBody = qs("users-table-body");
  els.userModal = qs("user-modal");
  els.userModalTitle = qs("user-modal-title");
  els.userModalSubtitle = qs("user-modal-subtitle");
  els.userModalBody = qs("user-modal-body");
  els.userDownload = qs("user-download");
  els.userClose = qs("user-close");

  bindEvents();
  updatePreview();
  populateStageFilter();

  const saved = getToken();
  if (saved) {
    els.tokenInput.value = saved;
    ensureAudience();
  }
}

document.addEventListener("DOMContentLoaded", init);
