// Мини-приложение Фоксинбург: 6 модулей.
// Работает внутри MAX Mini App и как обычная веб-страница.

const API = "";
let INFO = null;

async function getJSON(url) {
  const r = await fetch(API + url);
  return r.json();
}
async function postJSON(url, body) {
  const r = await fetch(API + url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return r.json();
}

// --- Navigation ---

function goTo(sec) {
  // Hide more menu
  document.getElementById("more-menu").style.display = "none";

  // Show section
  document.querySelectorAll(".section").forEach(s => s.classList.remove("active"));
  const el = document.getElementById("sec-" + sec);
  if (el) {
    el.classList.add("active");
    window.scrollTo(0, 0);
  }

  // Update nav
  document.querySelectorAll(".nav-item").forEach(n => n.classList.remove("active"));
  const navBtn = document.querySelector(`.nav-item[data-sec="${sec}"]`);
  if (navBtn) navBtn.classList.add("active");
}

// Bottom nav clicks
document.querySelectorAll(".nav-item").forEach(btn => {
  btn.addEventListener("click", () => {
    const sec = btn.dataset.sec;
    if (sec === "more") {
      const menu = document.getElementById("more-menu");
      menu.style.display = menu.style.display === "none" ? "block" : "none";
      return;
    }
    goTo(sec);
  });
});

// Close more menu on tap outside
document.addEventListener("click", (e) => {
  if (!e.target.closest(".nav-item[data-sec='more']") && !e.target.closest("#more-menu")) {
    document.getElementById("more-menu").style.display = "none";
  }
});

// Handle URL hash for deep linking from bot
function handleHash() {
  const hash = window.location.hash.replace("#", "");
  if (hash) goTo(hash);
}
window.addEventListener("hashchange", handleHash);

// --- Render: Home Promos ---

function renderHomePromos() {
  const el = document.getElementById("home-promos");
  const promos = (INFO && INFO.promos) || [];
  if (!promos.length) { el.innerHTML = ""; return; }
  el.innerHTML = promos.map(p =>
    `<div class="promo-card">
      <h3>🎁 Акция</h3>
      <p style="font-size:14px;">${p}</p>
    </div>`
  ).join("");
}

// --- Render: Advantages ---

function renderAdvantages() {
  const el = document.getElementById("advantages-list");
  const items = (INFO && INFO.advantages) || [];
  const icons = ["📜", "🏆", "👥", "👩‍🏫", "📊", "📱"];
  el.innerHTML = items.map((a, i) =>
    `<div style="display:flex;gap:10px;align-items:flex-start;margin-bottom:12px;">
      <span style="font-size:22px;flex-shrink:0;width:28px;">${icons[i] || "✨"}</span>
      <span style="flex:1;min-width:0;">
        <b style="font-size:13px;color:#392852;display:block;margin-bottom:2px;">${a.title || ""}</b>
        <span style="font-size:12px;color:#6f6883;line-height:1.4;">${a.text || ""}</span>
      </span>
    </div>`
  ).join("");
}

// --- Render: Courses ---

function renderCourses() {
  const el = document.getElementById("courses-list");
  const courses = (INFO && INFO.courses) || [];
  const ageProg = (INFO && INFO.age_programs) || [];

  // Age programs
  let html = "<h3 style='margin-bottom:10px; color:var(--purple2);'>По возрасту</h3>";
  html += ageProg.map(p =>
    `<div class="card course-card">
      <span class="pill pill-yellow">${p.age || ""}</span>
      <h3 style="margin-top:6px;">${p.name || ""}</h3>
      <p class="meta">${p.text || ""}</p>
      ${p.url ? `<a href="${p.url}" target="_blank" style="font-size:13px;">Подробнее на сайте →</a>` : ""}
      <button class="btn btn-ghost btn-sm" style="margin-top:8px;" onclick="signupFor('${(p.name||"").replace(/'/g,"\\'")}')">Записаться</button>
    </div>`
  ).join("");

  // Courses
  html += "<h3 style='margin:16px 0 10px; color:var(--purple2);'>Все курсы</h3>";
  html += courses.map(c => {
    const desc = c.description || c.note || "";
    const age = c.ages || "";
    return `<div class="card course-card">
      ${age ? `<span class="pill pill-yellow">${age}</span>` : ""}
      <h3 style="margin-top:6px;">${c.name || ""}</h3>
      ${desc ? `<p class="meta">${desc}</p>` : ""}
      ${c.price ? `<span class="pill pill-orange" style="margin-top:6px;">${c.price}</span>` : ""}
      ${c.teacher ? `<p class="meta">Педагог: ${c.teacher}</p>` : ""}
      ${c.trial_price ? `<p class="meta">${c.trial_price}</p>` : ""}
      ${c.url ? `<a href="${c.url}" target="_blank" style="font-size:13px; display:block; margin-top:6px;">Подробнее →</a>` : ""}
      <button class="btn btn-ghost btn-sm" style="margin-top:8px;" onclick="signupFor('${(c.name||"").replace(/'/g,"\\'")}')">Записаться</button>
    </div>`;
  }).join("");

  // Formats
  const formats = (INFO && INFO.formats) || [];
  html += "<h3 style='margin:16px 0 10px; color:var(--purple2);'>Форматы занятий</h3>";
  html += formats.map(f =>
    `<div class="card">
      <h3>${f.name || ""}</h3>
      <p class="meta">${f.location || ""}</p>
      <ul style="margin:8px 0 8px 18px; font-size:13px;">
        ${(f.details || []).map(d => `<li>${d}</li>`).join("")}
      </ul>
      ${f.price ? `<span class="pill pill-orange">${f.price}</span>` : ""}
    </div>`
  ).join("");

  el.innerHTML = html;
}

// --- Render: Summer Academy ---

function renderSummer() {
  const el = document.getElementById("summer-info");
  const sa = INFO && INFO.summer_academy;
  if (!sa || !sa.name) {
    el.innerHTML = '<div class="card"><p>Информация скоро появится</p></div>';
    return;
  }
  const shifts = sa.shifts || [];
  el.innerHTML = `
    <div class="card" style="background: linear-gradient(135deg, #ff9a56, var(--orange)); color:#fff;">
      <h3 style="color:#fff; font-size:18px;">${sa.name}</h3>
      <p style="margin:6px 0;">🕐 ${sa.time || ""}</p>
      <p>👦 ${sa.ages || ""}</p>
      <p style="font-size:18px; font-weight:700; margin-top:8px;">${sa.price || ""}</p>
      <p style="font-size:13px; opacity:.9; margin-top:4px;">${sa.note || ""}</p>
    </div>
    <h3 style="margin:8px 0 10px; color:var(--purple);">Смены</h3>
    ${shifts.map(s => {
      const parts = s.split(": ");
      const title = parts[0] || s;
      const desc = parts[1] || "";
      return `<div class="card shift-card">
        <h3>${title}</h3>
        ${desc ? `<p class="meta">${desc}</p>` : ""}
      </div>`;
    }).join("")}
    <button class="btn btn-orange" style="margin-top:4px;" onclick="signupFor('Летняя Академия')">
      Записаться в Академию ☀️
    </button>
  `;
}

// --- Render: Branches ---

function renderBranches() {
  const el = document.getElementById("branches-list");
  const branches = (INFO && INFO.branches) || [];
  el.innerHTML = branches.map(b =>
    `<div class="card branch-card">
      <h3>${b.name || ""}</h3>
      <p style="margin:6px 0;">📍 ${b.address || ""}</p>
      <p>☎️ <a href="tel:${b.phone_tel || ""}">${b.phone || ""}</a></p>
      <p class="meta">🕐 ${b.work_hours || ""}</p>
      ${b.maps ? `<a href="${b.maps}" target="_blank" class="btn btn-ghost btn-sm" style="margin-top:10px;">Построить маршрут 🗺</a>` : ""}
    </div>`
  ).join("") + `
    <div class="card">
      <h3>Онлайн</h3>
      <p class="meta">Занятия из любой точки мира</p>
      <button class="btn btn-ghost btn-sm" style="margin-top:8px;" onclick="signupFor('Онлайн')">Записаться онлайн</button>
    </div>
  `;
}

// --- Render: FAQ ---

function renderFAQ() {
  const el = document.getElementById("faq-list");
  const faq = (INFO && INFO.faq) || [];
  el.innerHTML = faq.map((item, i) =>
    `<div class="faq-item">
      <div class="faq-q" onclick="toggleFaq(${i})" id="faq-q-${i}">${item.q || ""}</div>
      <div class="faq-a" id="faq-a-${i}">${item.a || ""}</div>
    </div>`
  ).join("");
}

function toggleFaq(i) {
  const q = document.getElementById("faq-q-" + i);
  const a = document.getElementById("faq-a-" + i);
  q.classList.toggle("open");
  a.classList.toggle("open");
}

// --- Signup form ---

function signupFor(course) {
  document.getElementById("lf-course").value = course || "";
  goTo("signup");
}

function startParam() {
  const q = new URLSearchParams(window.location.search);
  const fromUrl = q.get("startapp") || q.get("start_param") || q.get("section");
  if (fromUrl) return fromUrl;
  try {
    const wa = window.WebApp || (window.max && window.max.WebApp);
    return (wa && (wa.initDataUnsafe?.start_param || wa.initDataUnsafe?.startParam)) || "";
  } catch (e) {
    return "";
  }
}

document.getElementById("lf-submit").addEventListener("click", async () => {
  const status = document.getElementById("lf-status");
  const parent = document.getElementById("lf-parent").value.trim();
  const phone = document.getElementById("lf-phone").value.trim();

  if (!parent || !phone) {
    showStatus("Пожалуйста, укажите имя и телефон.", false);
    return;
  }

  showStatus("Отправляю...", true);

  const body = {
    fio_parent: parent,
    fio_child: document.getElementById("lf-child").value.trim(),
    birthday: document.getElementById("lf-birthday").value.trim(),
    phone: phone,
    branch: document.getElementById("lf-branch").value,
    comment: document.getElementById("lf-comment").value.trim(),
    course: document.getElementById("lf-course").value,
    start_param: startParam(),
  };

  try {
    const res = await postJSON("/api/miniapp/lead", body);
    if (res.ok) {
      showStatus("Готово! ✅ Заявка отправлена, администратор скоро свяжется с вами.", true);
      // Clear form
      ["lf-parent","lf-child","lf-birthday","lf-phone","lf-comment"].forEach(id => {
        document.getElementById(id).value = "";
      });
      document.getElementById("lf-branch").selectedIndex = 0;
      document.getElementById("lf-course").value = "";
    } else {
      showStatus("Ошибка: " + (res.error || "попробуйте позже"), false);
    }
  } catch (e) {
    showStatus("Не удалось отправить. Попробуйте позже или позвоните нам.", false);
  }
});

function showStatus(msg, ok) {
  const s = document.getElementById("lf-status");
  s.textContent = msg;
  s.style.display = "block";
  s.className = "status " + (ok ? "status-ok" : "status-err");
}

// --- MAX Mini App bridge ---

function initMaxBridge() {
  try {
    const wa = window.WebApp || (window.max && window.max.WebApp);
    if (wa && wa.ready) wa.ready();
  } catch (e) { /* fallback */ }
}

// --- Init ---

(async function init() {
  initMaxBridge();
  try {
    INFO = await getJSON("/api/miniapp/info");
    renderHomePromos();
    renderAdvantages();
    renderCourses();
    renderSummer();
    renderBranches();
    renderFAQ();
  } catch (e) {
    console.error("Failed to load data:", e);
  }

  // Handle deep link
  const sp = startParam();
  if (sp && ["courses","signup","summer","branches","faq"].includes(sp)) {
    goTo(sp);
  }
  handleHash();
})();
