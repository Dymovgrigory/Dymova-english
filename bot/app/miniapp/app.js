// Мини-приложение Фоксинбург: меню мини-приложений.
// Экраны: меню, подбор курса, запись, помощь с домашкой, каталог, филиалы, кабинет.
// Работает внутри MAX Mini App (если доступен мост) и как обычная веб-страница.

const API = ""; // тот же origin, что и бот
let MINIAPP_USER_ID = "";
let MINIAPP_INIT_DATA = "";
let ACCESS = { has_identity: false, registered: false, locked: false, message: "" };

// Личность подтверждается подписью initData на бэкенде. user_id остаётся
// только для локальной отладки (MINIAPP_AUTH_REQUIRED=false) и сам по себе
// никаких прав не даёт.
function authHeaders() {
  if (!MINIAPP_INIT_DATA) return {};
  return {
    "X-Miniapp-Init-Data": MINIAPP_INIT_DATA,
    "X-Miniapp-Platform": "max",
  };
}

// Данные приходят из базы знаний и от LLM — в innerHTML без экранирования
// их вставлять нельзя.
function esc(value) {
  return String(value == null ? "" : value).replace(/[&<>"']/g, (ch) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch])
  );
}

async function getJSON(url) {
  const u = new URL(API + url, window.location.origin);
  if (MINIAPP_USER_ID) u.searchParams.set("user_id", MINIAPP_USER_ID);
  const r = await fetch(u.toString(), { headers: authHeaders() });
  return r.json();
}
async function postJSON(url, body) {
  const payload = { ...body };
  if (MINIAPP_USER_ID) payload.user_id = MINIAPP_USER_ID;
  const r = await fetch(API + url, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(payload),
  });
  return r.json();
}

let INFO = null;

// --- Навигация по экранам ---
const SCREENS = ["menu", "select", "signup", "homework", "catalog", "branches", "cabinet"];
function showScreen(name) {
  SCREENS.forEach((s) => {
    document.getElementById("screen-" + s).classList.toggle("hidden", s !== name);
  });
  window.scrollTo({ top: 0, behavior: "smooth" });
  if (location.hash !== "#" + name) history.replaceState(null, "", "#" + name);
}
document.querySelectorAll("[data-go]").forEach((el) => {
  el.addEventListener("click", () => showScreen(el.dataset.go));
});

// --- Помощник по выбору ---
document.getElementById("sel-go").addEventListener("click", async () => {
  const age = document.getElementById("sel-age").value;
  const fmt = document.getElementById("sel-format").value;
  const box = document.getElementById("sel-results");
  box.innerHTML = "<p class='muted'>Подбираю...</p>";
  const data = await getJSON(`/api/miniapp/recommend?age=${encodeURIComponent(age)}&fmt=${encodeURIComponent(fmt)}`);
  const items = data.recommendations || [];
  if (!items.length) {
    box.innerHTML = "<p class='muted'>Не нашёл точного совпадения — оставьте заявку, поможем подобрать.</p>";
  } else {
    box.innerHTML =
      "<h2>Подходящие программы</h2>" +
      items
        .map(
          (p) =>
            `<div class="card course-card"><span class="pill">${esc(p.age || "любой возраст")}</span>
             <h2 style="margin-top:8px">${esc(p.name || "")}</h2>
             <p class="muted">${esc(p.text || "")}</p></div>`
        )
        .join("");
  }
  openLeadForm({ age });
});

// --- Каталог курсов ---
function renderCatalog() {
  const el = document.getElementById("catalog");
  const courses = (INFO && INFO.courses) || [];
  const formats = (INFO && INFO.formats) || [];
  el.innerHTML =
    "<h2>Форматы занятий</h2>" +
    formats
      .map(
        (f) =>
          `<div class="card"><h2>${esc(f.name)}</h2><p class="muted">${esc(f.location || "")}</p>
           <ul style="margin:8px 0 8px 18px; font-size:14px;">${(f.details || [])
             .map((d) => `<li>${esc(d)}</li>`)
             .join("")}</ul>
           <span class="pill">${esc(f.price || "")}</span></div>`
      )
      .join("") +
    "<h2>Курсы</h2>" +
    courses
      .map(
        (c) =>
          `<div class="card course-card"><h2>${esc(c.name)}</h2>
           <p class="muted">${esc(c.description || c.note || "")}</p>
           ${c.price ? `<span class="pill">${esc(c.price)}</span>` : ""}
           ${c.teacher ? `<p class="muted" style="margin-top:6px">Педагог: ${esc(c.teacher)}</p>` : ""}</div>`
      )
      .join("");
}

// --- Филиалы ---
function renderBranches() {
  const el = document.getElementById("branches");
  const branches = (INFO && INFO.branches) || [];
  el.innerHTML =
    "<h2>Наши филиалы</h2>" +
    branches
      .map(
        (b) =>
          `<div class="card"><h2>${esc(b.name)}</h2>
           <p>${IC_PIN}<a href="${esc(b.maps)}" target="_blank" rel="noopener">${esc(b.address)}</a></p>
           <p>${IC_PHONE}<a href="tel:${esc(b.phone_tel)}">${esc(b.phone)}</a></p>
           <p class="muted">${IC_CLOCK}${esc(b.work_hours || "")}</p></div>`
      )
      .join("");
}

// Иконки списков — тот же язык, что и на плитках меню. Эмодзи не годятся:
// они рисуются шрифтом системы, то есть выглядят по-разному на каждом
// устройстве и к фирменному стилю школы отношения не имеют.
const IC_ATTRS =
  'class="meta__ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
  'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"';
const IC_PIN =
  `<svg ${IC_ATTRS}><path d="M12 21s7-5.4 7-11a7 7 0 1 0-14 0c0 5.6 7 11 7 11Z"/>` +
  '<circle cx="12" cy="10" r="2.6"/></svg>';
const IC_PHONE =
  `<svg ${IC_ATTRS}><path d="M5 4h3l2 5-2 1.5a12 12 0 0 0 5.5 5.5L15 14l5 2v3a2 2 0 0 1-2.2 2A16.5 16.5 0 0 1 3 6.2 2 2 0 0 1 5 4Z"/></svg>`;
const IC_CLOCK =
  `<svg ${IC_ATTRS}><circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 1.8"/></svg>`;

// --- Форма заявки ---
function openLeadForm(prefill = {}) {
  showScreen("signup");
  if (prefill.age) document.getElementById("lf-age").value = prefill.age;
}

document.getElementById("cabinet-signup").addEventListener("click", () => openLeadForm());

document.getElementById("lf-submit").addEventListener("click", async () => {
  if (ACCESS.locked) {
    showStatus(ACCESS.message || "Сначала зарегистрируйтесь в чате.", false);
    return;
  }
  const courseKind = document.getElementById("lf-course-kind").value;
  const experience = document.getElementById("lf-experience").value;
  const userComment = document.getElementById("lf-comment").value.trim();
  const commentParts = [];
  if (courseKind) commentParts.push("Раздел: " + courseKind);
  if (experience) commentParts.push("Опыт: " + experience);
  if (userComment) commentParts.push(userComment);
  const body = {
    fio_parent: document.getElementById("lf-parent").value.trim(),
    fio_child: document.getElementById("lf-child").value.trim(),
    age: document.getElementById("lf-age").value.trim(),
    birthday: document.getElementById("lf-birthday").value,
    phone: document.getElementById("lf-phone").value.trim(),
    branch: document.getElementById("lf-branch").value,
    comment: commentParts.join("; ").slice(0, 255),
  };
  if (!body.fio_parent || !body.phone || !body.fio_child || !body.birthday || !experience) {
    showStatus("Пожалуйста, заполните обязательные поля: имя, телефон, имя и дату рождения ребёнка, опыт занятий.", false);
    return;
  }
  showStatus("Отправляю...", true);
  const res = await postJSON("/api/miniapp/lead", body);
  if (res.ok) {
    showStatus("Готово — заявка отправлена. Администратор скоро свяжется с вами.", true);
  } else {
    showStatus("Не удалось отправить заявку: " + (res.error || "попробуйте позже или позвоните нам."), false);
  }
});

function showStatus(msg, ok) {
  const s = document.getElementById("lf-status");
  s.textContent = msg;
  s.classList.remove("hidden");
  s.style.background = ok ? "#e7f7ec" : "#fdecec";
}

// --- Помощь с домашкой ---
document.getElementById("hw-file").addEventListener("change", (e) => {
  const file = e.target.files && e.target.files[0];
  const img = document.getElementById("hw-preview");
  if (file) {
    img.src = URL.createObjectURL(file);
    img.style.display = "block";
  } else {
    img.style.display = "none";
  }
});

function hwStatus(msg, ok) {
  const s = document.getElementById("hw-status");
  s.textContent = msg;
  s.classList.remove("hidden");
  s.style.background = ok ? "#e7f7ec" : "#fdecec";
}

document.getElementById("hw-submit").addEventListener("click", async () => {
  const fileInput = document.getElementById("hw-file");
  const file = fileInput.files && fileInput.files[0];
  const answerBox = document.getElementById("hw-answer");
  answerBox.classList.add("hidden");
  if (!file) {
    hwStatus("Пожалуйста, прикрепите фото задания.", false);
    return;
  }
  if (ACCESS.locked) {
    hwStatus(ACCESS.message || "Сначала зарегистрируйтесь в чате.", false);
    return;
  }
  const btn = document.getElementById("hw-submit");
  btn.disabled = true;
  hwStatus("Фокси разбирает задание... Обычно это 10–20 секунд.", true);
  try {
    const fd = new FormData();
    fd.append("image", file);
    fd.append("note", document.getElementById("hw-note").value.trim());
    if (MINIAPP_USER_ID) fd.append("user_id", MINIAPP_USER_ID);
    if (MINIAPP_INIT_DATA) fd.append("init_data", MINIAPP_INIT_DATA);
    const r = await fetch(API + "/api/miniapp/homework", {
      method: "POST",
      headers: authHeaders(),
      body: fd,
    });
    const res = await r.json();
    if (res.ok && res.explanation) {
      hwStatus("Готово! Вот разбор:", true);
      answerBox.textContent = res.explanation;
      answerBox.classList.remove("hidden");
    } else {
      hwStatus("Не получилось разобрать фото: " + (res.error || res.detail || "попробуйте снимок почище."), false);
    }
  } catch (e) {
    hwStatus("Ошибка сети — попробуйте ещё раз.", false);
  } finally {
    btn.disabled = false;
  }
});

// --- MAX Mini App bridge (приветствие по имени, если доступно) ---
function initMaxBridge() {
  try {
    const wa = window.WebApp || (window.max && window.max.WebApp);
    if (!wa) return;
    // Подписанная строка — единственное, что бэкенд принимает как личность.
    MINIAPP_INIT_DATA = wa.initData || "";
    if (wa.initDataUnsafe && wa.initDataUnsafe.user) {
      MINIAPP_USER_ID = String(wa.initDataUnsafe.user.id || "");
      const name = wa.initDataUnsafe.user.first_name || "";
      if (name) {
        document.getElementById("cabinet-greeting").textContent = `Здравствуйте, ${name}!`;
      }
    }
  } catch (e) {
    /* работаем как обычная веб-страница */
  }
}

(async function init() {
  initMaxBridge();
  // поддержка старых ссылок вида #signup / #homework
  const hash = (location.hash || "").replace("#", "");
  if (SCREENS.includes(hash) && hash !== "menu") showScreen(hash);
  try {
    ACCESS = await getJSON("/api/miniapp/access");
    INFO = await getJSON("/api/miniapp/info");
    renderCatalog();
    renderBranches();
  } catch (e) {
    console.error(e);
  }
})();
