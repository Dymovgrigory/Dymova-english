// Мини-приложение Фоксинбург: меню мини-приложений.
// Экраны: меню, подбор курса, запись, помощь с домашкой, каталог, филиалы, кабинет.
// Работает внутри MAX Mini App (если доступен мост) и как обычная веб-страница.

const API = ""; // тот же origin, что и бот
let MINIAPP_USER_ID = "";
let ACCESS = { has_identity: false, registered: false, locked: false, message: "" };

async function getJSON(url) {
  const u = new URL(API + url, window.location.origin);
  if (MINIAPP_USER_ID) u.searchParams.set("user_id", MINIAPP_USER_ID);
  const r = await fetch(u.toString());
  return r.json();
}
async function postJSON(url, body) {
  const payload = { ...body };
  if (MINIAPP_USER_ID) payload.user_id = MINIAPP_USER_ID;
  const r = await fetch(API + url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
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
            `<div class="card course-card"><span class="pill">${p.age || "любой возраст"}</span>
             <h2 style="margin-top:8px">${p.name || ""}</h2>
             <p class="muted">${p.text || ""}</p></div>`
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
          `<div class="card"><h2>${f.name}</h2><p class="muted">${f.location || ""}</p>
           <ul style="margin:8px 0 8px 18px; font-size:14px;">${(f.details || [])
             .map((d) => `<li>${d}</li>`)
             .join("")}</ul>
           <span class="pill">${f.price || ""}</span></div>`
      )
      .join("") +
    "<h2>Курсы</h2>" +
    courses
      .map(
        (c) =>
          `<div class="card course-card"><h2>${c.name}</h2>
           <p class="muted">${c.description || c.note || ""}</p>
           ${c.price ? `<span class="pill">${c.price}</span>` : ""}
           ${c.teacher ? `<p class="muted" style="margin-top:6px">Педагог: ${c.teacher}</p>` : ""}</div>`
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
          `<div class="card"><h2>${b.name}</h2>
           <p>📍 <a href="${b.maps}" target="_blank">${b.address}</a></p>
           <p>☎ <a href="tel:${b.phone_tel}">${b.phone}</a></p>
           <p class="muted">🕘 ${b.work_hours || ""}</p></div>`
      )
      .join("");
}

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
  const body = {
    fio_parent: document.getElementById("lf-parent").value.trim(),
    fio_child: document.getElementById("lf-child").value.trim(),
    age: document.getElementById("lf-age").value.trim(),
    phone: document.getElementById("lf-phone").value.trim(),
    branch: document.getElementById("lf-branch").value,
    comment: document.getElementById("lf-comment").value.trim(),
  };
  if (!body.fio_parent || !body.phone) {
    showStatus("Пожалуйста, укажите имя и телефон.", false);
    return;
  }
  showStatus("Отправляю...", true);
  const res = await postJSON("/api/miniapp/lead", body);
  if (res.ok) {
    showStatus("Готово! ✅ Заявка отправлена, администратор скоро свяжется с вами.", true);
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
    const r = await fetch(API + "/api/miniapp/homework", { method: "POST", body: fd });
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
    if (wa && wa.initDataUnsafe && wa.initDataUnsafe.user) {
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
