const API = "";
const STORAGE_KEY = "foxinburg_admin_token";

let audience = null;

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
  const token = getToken();
  return {
    "Content-Type": "application/json",
    "X-Admin-Token": token,
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
  if (text) parts.push(text);
  else parts.push("Текст рассылки появится здесь.");
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

function requireToken() {
  let token = getToken();
  if (!token) {
    token = setToken(window.prompt("Введите X-Admin-Token для доступа к рассылкам:", "") || "");
  }
  if (!token) {
    showError("Требуется административный токен.");
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

async function sendBroadcast(isTest) {
  const text = els.messageText.value.trim();
  if (!text) {
    showError("Введите текст рассылки.");
    return;
  }
  const buttonText = els.buttonText.value.trim();
  const buttonUrl = els.buttonUrl.value.trim();
  if (Boolean(buttonText) !== Boolean(buttonUrl)) {
    showError("Кнопка должна быть заполнена полностью: текст и ссылка.");
    return;
  }
  const segment = currentSegment();
  const payload = {
    text,
    segment,
    button_text: buttonText || undefined,
    button_url: buttonUrl || undefined,
  };
  if (segment === "course") payload.course = els.courseSelect.value;
  if (segment === "branch") payload.branch = els.branchSelect.value;
  const count = parseInt(els.recipientCount.textContent.replace(/\D+/g, ""), 10) || 0;
  if (!confirm(isTest ? "Отправить тест администраторам?" : `Отправить рассылку ${count} получателям?`)) {
    return;
  }
  try {
    const url = isTest ? "/admin/broadcast/test" : "/admin/broadcast/send";
    const data = await requestJSON(url, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    if (isTest) {
      showResult(`Тест отправлен: доставлено ${data.delivered} из ${data.total}, ошибок ${data.failed}.`);
    } else {
      showResult(`Рассылка отправлена: доставлено ${data.delivered} из ${data.total}, ошибок ${data.failed}.`);
    }
    clearError();
  } catch (err) {
    if (String(err.message) === "401") {
      setToken("");
      els.loginCard.classList.remove("hidden");
      els.appShell.classList.add("hidden");
      showError("Сессия администратора истекла или токен неверный.");
      return;
    }
    showError(`Не удалось отправить рассылку: ${err.message}`);
  }
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
  bindEvents();
  updatePreview();
  const saved = getToken();
  if (saved) {
    els.tokenInput.value = saved;
    ensureAudience();
  }
}

document.addEventListener("DOMContentLoaded", init);
