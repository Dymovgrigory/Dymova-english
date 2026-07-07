// Мини-приложение Фоксинбург: витрина курсов, помощник по выбору, личный кабинет.
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

// --- Вкладки ---
document.querySelectorAll(".tab").forEach((t) => {
  t.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((x) => x.classList.remove("active"));
    t.classList.add("active");
    const name = t.dataset.tab;
    ["select", "catalog", "branches", "cabinet"].forEach((s) => {
      document.getElementById("tab-" + s).classList.toggle("hidden", s !== name);
    });
  });
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

function applyAccessState() {
  const notice = document.querySelector("#tab-cabinet .notice");
  if (!notice) return;
  if (ACCESS.locked) {
    notice.textContent = ACCESS.message;
    return;
  }
  if (!ACCESS.has_identity) {
    notice.textContent =
      "Откройте miniapp внутри MAX, чтобы связать профиль. После регистрации здесь появятся кабинет, домашка и онлайн-запись.";
  }
}

// --- Форма заявки ---
function openLeadForm(prefill = {}) {
  if (ACCESS.locked) {
    showStatus(ACCESS.message || "Сначала зарегистрируйтесь в чате.", false);
    return;
  }
  const form = document.getElementById("lead-form");
  form.classList.remove("hidden");
  if (prefill.age) document.getElementById("lf-age").value = prefill.age;
  form.scrollIntoView({ behavior: "smooth" });
}

document.getElementById("cabinet-signup").addEventListener("click", () => openLeadForm());

document.getElementById("lf-submit").addEventListener("click", async () => {
  if (ACCESS.locked) {
    showStatus(ACCESS.message || "Сначала зарегистрируйтесь в чате.", false);
    return;
  }
  const status = document.getElementById("lf-status");
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
  try {
    ACCESS = await getJSON("/api/miniapp/access");
    applyAccessState();
    INFO = await getJSON("/api/miniapp/info");
    renderCatalog();
    renderBranches();
  } catch (e) {
    console.error(e);
  }
})();
