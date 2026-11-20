// CampusYamu UI mockup. Vanilla JS, talks to the /v1 API (mock or live via server.js).
// Visual style: friendly app look in navy, royal blue, lavender and mustard, with flat illustrations.
// Interface text lives in i18n.js (Sinhala, Tamil, English); API data is shown as sent.
import { LANGS, t, setLang, getLang } from "./i18n.js";

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const app = $("#app");
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ---------------------------------------------------------------- language
// The language is picked on the first screen and remembered on this device.
const savedLang = (() => { try { return localStorage.getItem("cy.lang"); } catch { return null; } })();
let langChosen = LANGS.some((l) => l.id === savedLang);
setLang(langChosen ? savedLang : "en");

// ---------------------------------------------------------------- theme
// Light or dark. Follows the device until the student picks one (sun/moon button or the account page),
// then remembers it on this device (cy.theme). index.html applies a saved choice before the first paint.
const DARK_MQ = matchMedia("(prefers-color-scheme: dark)");
const getTheme = () => { try { const v = localStorage.getItem("cy.theme"); return v === "light" || v === "dark" ? v : "system"; } catch { return "system"; } };
const isDark = () => document.documentElement.dataset.theme === "dark" || (!document.documentElement.dataset.theme && DARK_MQ.matches);
function applyTheme(choice) {
  if (choice === "system") document.documentElement.removeAttribute("data-theme");
  else document.documentElement.dataset.theme = choice;
  $$('meta[name="theme-color"]').forEach((m) => (m.content = isDark() ? "#0B0E2B" : "#FAF9FF"));
  const label = t(isDark() ? "theme.toLight" : "theme.toDark");
  $$(".theme-btn").forEach((b) => { b.innerHTML = isDark() ? I.sun : I.moon; b.setAttribute("aria-label", label); b.title = label; });
  $$("[data-theme-opt]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.themeOpt === choice));
}
function setTheme(choice) {
  try { if (choice === "system") localStorage.removeItem("cy.theme"); else localStorage.setItem("cy.theme", choice); } catch {}
  applyTheme(choice);
}
DARK_MQ.addEventListener("change", () => applyTheme(getTheme()));
const themeBtn = () => {
  const label = esc(t(isDark() ? "theme.toLight" : "theme.toDark"));
  return `<button class="icon-btn theme-btn" type="button" aria-label="${label}" title="${label}">${isDark() ? I.sun : I.moon}</button>`;
};
document.addEventListener("click", (e) => {
  if (e.target.closest(".theme-btn")) { setTheme(isDark() ? "light" : "dark"); return; }
  const opt = e.target.closest("[data-theme-opt]");
  if (opt) setTheme(opt.dataset.themeOpt);
});

// ---------------------------------------------------------------- state
const state = {
  signedIn: (() => { try { return sessionStorage.getItem("cy.signed") === "1"; } catch { return false; } })(),
  options: null,
  report: null,
  me: null,
  band: "strong",
  ranking: "distance",
  query: "",
  showAll: false,
  step: 0,
  form: {
    stream: "Physical Science",
    al: [["Combined Mathematics", "A"], ["Physics", "B"], ["Chemistry", "C"]],
    ol: { Science: "B", English: "B", Mathematics: "A" },
    cgt: 40,
    z_score: "1.5600",
    admission_district: "Gampaha",
    home_district: "Gampaha",
    ds_division: "Minuwangoda",
    preferences: "engineering, design",
    use_llm: false,
  },
  pendingRun: null,
};

const BAND_IDS = ["strong", "competitive", "reach", "unlikely", "no_history"];
const bandLabel = (id) => t("bands")[id]?.[0] ?? id;
const bandDesc = (id) => t("bands")[id]?.[1] ?? "";
const BAND_COLOR = { strong: "var(--blue)", competitive: "var(--lav)", reach: "var(--mustard)", unlikely: "color-mix(in srgb, var(--ink) 22%, var(--bg))", no_history: "var(--line)" };

// ---------------------------------------------------------------- api
async function api(path, opts = {}) {
  const res = await fetch(path, {
    method: opts.method || "GET",
    headers: { "content-type": "application/json" },
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw Object.assign(new Error(data.detail || `Request failed (${res.status})`), { status: res.status });
  return data;
}
const loadOptions = async () => (state.options ??= await api("/v1/options"));
const loadMe = async () => (state.me = await api("/v1/me"));
async function loadReport() {
  if (state.report) return state.report;
  try { state.report = (await api("/v1/me/results")).report; } catch (e) { if (e.status !== 404) throw e; }
  return state.report;
}

function toast(msg) {
  const el = $("#toast");
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.remove("show"), 2800);
}

// ---------------------------------------------------------------- icons
const I = {
  search: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>',
  back: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg>',
  ne: '<svg class="arr" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>',
  spark: '<svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2.5l2.1 6.4 6.4 2.1-6.4 2.1L12 19.5l-2.1-6.4L3.5 11l6.4-2.1z"/></svg>',
  down: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M6 13l6 6 6-6"/></svg>',
  send: '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h13M13 6l6 6-6 6"/></svg>',
  check: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>',
  trash: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/></svg>',
  chat: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.4A8 8 0 1 1 21 12z"/></svg>',
  edit: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20h4L19 9l-4-4L4 16z"/></svg>',
  grid: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><rect x="4" y="4" width="7" height="7" rx="2"/><rect x="13" y="4" width="7" height="7" rx="2"/><rect x="4" y="13" width="7" height="7" rx="2"/><rect x="13" y="13" width="7" height="7" rx="2"/></svg>',
  list: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><path d="M9 6h11M9 12h11M9 18h11M4 6h1M4 12h1M4 18h1"/></svg>',
  sun: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4"/></svg>',
  moon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/></svg>',
  globe: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.6-3.8-9S9.5 5.6 12 3z"/></svg>',
};

// the logo: a Y that is a fork in the road, with the AI sparkle on the branch to take
const LOGO = `<svg class="mark" viewBox="0 0 100 100" aria-hidden="true"><rect x="4" y="4" width="92" height="92" rx="26" fill="#4F6FE8"/><path d="M50 80 V54 M50 54 L31 30 M50 54 L64 37" stroke="#fff" stroke-width="10" stroke-linecap="round" stroke-linejoin="round" fill="none"/><path class="spark" d="M72 15 L75.5 25.5 L86 29 L75.5 32.5 L72 43 L68.5 32.5 L58 29 L68.5 25.5 Z" fill="#F2B84B"/></svg>`;
const brand = (href) => `<a class="brand" ${href ? `href="${href}"` : ""} aria-label="CampusYamu" lang="en">${LOGO}<span>campus<b>yamu</b></span></a>`;

// language switcher: a globe button with a small menu (top bar and sign-in)
function langMenu() {
  const cur = LANGS.find((l) => l.id === getLang());
  return `<div class="lang-menu">
    <button class="lang-btn" type="button" aria-haspopup="true" aria-expanded="false" aria-label="${esc(t("language"))}">${I.globe}<span lang="${cur.id}">${cur.short}</span></button>
    <div class="lang-pop" role="menu">${LANGS.map((l) => `<button type="button" role="menuitemradio" aria-checked="${l.id === cur.id}" data-lang="${l.id}" lang="${l.id}">${l.name}${l.id === cur.id ? I.check : ""}</button>`).join("")}</div>
  </div>`;
}
function chooseLang(id) {
  setLang(id);
  langChosen = true;
  try { localStorage.setItem("cy.lang", id); } catch {}
  if (location.hash.startsWith("#/lang")) location.hash = state.signedIn ? "#/results" : "#/home";
  else route();
}
document.addEventListener("click", (e) => {
  const pick = e.target.closest("[data-lang]");
  if (pick) { chooseLang(pick.dataset.lang); return; }
  const btn = e.target.closest(".lang-btn");
  $$(".lang-menu").forEach((m) => {
    const open = !!btn && m.contains(btn) && !m.classList.contains("open");
    m.classList.toggle("open", open);
    $(".lang-btn", m).setAttribute("aria-expanded", open);
  });
});
document.addEventListener("keydown", (e) => { if (e.key === "Escape") $$(".lang-menu.open").forEach((m) => m.classList.remove("open")); });

// ---------------------------------------------------------------- figures
// Drop illustrations into public/figures/ as <name>.webp, .png or .svg (see figures/README.md).
// The server lists what exists (/figures.json), so only real files are requested. Missing
// required slots show a labelled placeholder; missing optional ones (course cards) render nothing.
let FIGS = {};
const fig = (name, label, { optional = false } = {}) => {
  const file = FIGS[name];
  if (!file && optional) return "";
  return file
    ? `<div class="fig"><img src="/figures/${esc(file)}" alt="" loading="lazy"></div>`
    : `<div class="fig missing"><div class="fig-ph"><span class="spot"></span><b>${esc(label)}</b><span class="mono">figures/${name}.webp</span></div></div>`;
};
// which course-area figure a course gets
function area(name) {
  const n = name.toLowerCase();
  if (/tourism|hospitality/.test(n)) return "management"; // before "health" (e.g. Health Tourism)
  if (/medicine|dental|nursing|pharm|health|veterinary|medical|physiotherapy|radiograph|laboratory/.test(n)) return "medicine";
  if (/computer|information|software|data science|ict|artificial/.test(n)) return "it";
  if (/engineer|technology|quantity|architect|design|surveying|town/.test(n)) return "engineering";
  if (/management|commerce|account|business|financ|marketing|tourism|estate|hospitality|logistic/.test(n)) return "management";
  if (/arts|law|language|social|music|dance|drama|media|translation|islamic|buddhist/.test(n)) return "arts";
  return "science";
}

// ---------------------------------------------------------------- helpers
const fmtMin = (m) => (m == null ? "—" : m < 60 ? t("min", { n: Math.round(m) }) : t("hm", { h: Math.floor(m / 60), m: Math.round(m % 60) }));
const usageText = (u) => t("usage.today", { used: u.used, limit: u.limit });
const allRows = () => Object.values(state.report?.bands || {}).flat();
const findRow = (uni) => allRows().find((r) => r.uni_code === uni);
const abbrev = (s) => s.split(/\s+/).map((w) => w[0]).join("").slice(0, 4);
const pad2 = (n) => String(n).padStart(2, "0");
const afterPaint = (fn) => requestAnimationFrame(() => requestAnimationFrame(fn));

function countUp(root = document) {
  $$("[data-count]", root).forEach((el) => {
    const to = parseFloat(el.dataset.count);
    if (REDUCED) { el.textContent = to; return; }
    const t0 = performance.now(), dur = 1100 + Math.min(800, to * 8);
    const tick = (now) => {
      const p = Math.min(1, (now - t0) / dur);
      el.textContent = Math.round(to * (1 - Math.pow(1 - p, 4)));
      if (p < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
}
// sections rise in as they scroll into view (like the portfolio)
let revealObs;
function reveal(root = document) {
  revealObs ??= new IntersectionObserver((entries) => entries.forEach((e) => {
    if (e.isIntersecting) { e.target.classList.add("in"); revealObs.unobserve(e.target); }
  }), { rootMargin: "0px 0px -8% 0px" });
  $$(".reveal:not(.in)", root).forEach((el) => revealObs.observe(el));
}
function moveInk(tabs) {
  const ink = $(".ink", tabs), active = $("button.active", tabs);
  if (!ink || !active) return;
  ink.style.width = active.offsetWidth + "px";
  ink.style.transform = `translateX(${active.offsetLeft}px)`;
}

function markdown(md) {
  let html = "", inList = false;
  for (const raw of esc(md).split("\n")) {
    const line = raw.trim();
    const inline = (s) => s.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
    if (/^#{1,6}\s/.test(line)) { if (inList) { html += "</ul>"; inList = false; } html += `<h5>${inline(line.replace(/^#+\s/, ""))}</h5>`; }
    else if (/^[-*]\s/.test(line)) { if (!inList) { html += "<ul>"; inList = true; } html += `<li>${inline(line.slice(2))}</li>`; }
    else if (line) { if (inList) { html += "</ul>"; inList = false; } html += `<p>${inline(line)}</p>`; }
  }
  return html + (inList ? "</ul>" : "");
}

// ---------------------------------------------------------------- shell
function shell(active, inner) {
  const u = state.me?.usage?.chat;
  const link = (hash, id, text) => `<a href="${hash}" class="${active === id ? "active" : ""}">${text}</a>`;
  const tab = (hash, id, icon, text) => `<a href="${hash}" class="${active === id ? "active" : ""}"><span class="ic">${icon}</span><span>${text}</span></a>`;
  return `
  <div class="wrap">
    <header class="topbar"><div class="nav-inner">
      ${brand("#/results")}
      <nav class="nav">${link("#/form", "form", t("nav.results"))}${link("#/results", "results", t("nav.courses"))}${link("#/rankings", "rankings", t("nav.order"))}${link("#/me", "me", t("nav.chats"))}</nav>
      <div class="nav-right">
        ${u ? `<span class="usage" title="${esc(t("usage.title"))}"><span class="bar"><i style="width:${(u.used / u.limit) * 100}%"></i></span><span class="num">${usageText(u)}</span></span>` : ""}
        ${themeBtn()}${langMenu()}
        <a class="avatar" href="#/me" aria-label="${esc(t("account"))}">S</a>
      </div>
    </div></header>
    <main class="page view-enter">${inner}</main>
  </div>
  <nav class="tabbar" aria-label="Sections">
    ${tab("#/form", "form", I.edit, t("tab.results"))}${tab("#/results", "results", I.grid, t("tab.courses"))}${tab("#/rankings", "rankings", I.list, t("tab.order"))}${tab("#/me", "me", I.chat, t("tab.chats"))}
  </nav>`;
}
const headline = (plain, accent) => `${esc(plain)} <span class="accent">${esc(accent)}</span>`;

// ---------------------------------------------------------------- views
const views = {};

// ----- first screen: pick a language. Each option is written in its own script.
views.lang = async () => {
  app.innerHTML = `
  <div class="wrap"><section class="lang-page view-enter">
    ${brand()}
    <h1 class="lang-title">${LANGS.map((l) => `<span lang="${l.id}">${esc(l.choose)}</span>`).join("")}</h1>
    <div class="lang-cards">${LANGS.map((l, i) => `
      <button type="button" class="card lang-card reveal ${l.id === getLang() && langChosen ? "current" : ""}" style="--i:${i}" data-lang="${l.id}" lang="${l.id}">
        <span class="glyph g-${l.id}">${esc(l.short)}</span>
        <span class="txt"><b>${esc(l.name)}</b><span>${esc(l.hello)} ${esc(l.line)}</span></span>
        ${I.ne}
      </button>`).join("")}</div>
    <p class="faint lang-later">${LANGS.map((l) => `<span lang="${l.id}">${esc(l.later)}</span>`).join("")}</p>
  </section></div>`;
  reveal();
};

// ----- landing page: what CampusYamu is, before sign-in. Sign in is a button, not a wall.
// Numbers are real counts from the knowledge graph (data/processed/knowledge_graph/graph_data.json).
const LANDING_STATS = [126, 261, 20, 25, 6, 3];
const AREA_IDS = ["engineering", "medicine", "it", "management", "arts", "science"];
const STEP_FIGS = ["signin", "analysing", "area-engineering", "empty-chats"];
views.home = async () => {
  const [hA, hB] = [t("l.h1a"), t("l.h1b")];
  const pair = (k) => headline(...t(k));
  const steps = t("l.steps"), areas = t("l.areas"), stats = t("l.stats");
  app.innerHTML = `
  <div class="landing view-enter">
    <div class="wrap">
      <header class="topbar"><div class="nav-inner">
        ${brand("#/home")}
        <nav class="nav">
          <button type="button" data-scroll="l-how">${t("l.nav.how")}</button>
          <button type="button" data-scroll="l-areas">${t("l.nav.areas")}</button>
          <button type="button" data-scroll="l-faq">${t("l.nav.faq")}</button>
        </nav>
        <div class="nav-right">${themeBtn()}${langMenu()}<a class="btn sm" href="#/signin">${t("signin.btn")}</a></div>
      </div></header>

      <section class="l-hero">
        <div class="l-hero-text">
          <span class="l-kicker reveal">${I.spark}${t("l.kicker")}</span>
          <h1 class="reveal" style="--i:1">${esc(hA)}<br><span class="accent">${esc(hB)}</span></h1>
          <p class="l-sub reveal" style="--i:2">${t("l.sub")}</p>
          <div class="l-cta reveal" style="--i:3">
            <a class="btn" href="#/signin">${t("l.start")} ${I.ne}</a>
            <button type="button" class="btn outline" data-scroll="l-how">${t("l.how")} ${I.down}</button>
          </div>
          <ul class="l-trust reveal" style="--i:4">${t("l.trust").map((x) => `<li>${I.check}${x}</li>`).join("")}</ul>
        </div>
        <div class="l-hero-art reveal" style="--i:2">
          ${fig("signin", "Sign-in figure")}
          <span class="float f1"><span class="chip blue">${t("chance", { band: bandLabel("strong") })}</span></span>
          <span class="float f2"><b class="num">Z 1.5600</b></span>
          <span class="float f3">${I.spark}<span>${t("min", { n: 19 })}</span></span>
        </div>
      </section>
    </div>

    <section class="l-how" id="l-how" style="--n:${steps.length}"><div class="l-how-pin"><div class="wrap">
      <span class="label">${t("l.nav.how")}</span>
      <h2>${pair("l.howH")}</h2>
      <div class="l-how-grid">
        <div class="l-how-visual"><div class="card l-stage">
          <div class="l-stage-figs">${STEP_FIGS.map((f, i) => `<div class="l-stage-fig ${i === 0 ? "on" : ""}">${fig(f, f)}</div>`).join("")}</div>
          <div class="l-progress">${steps.map((_, i) => `<i class="${i === 0 ? "on" : ""}"><b></b></i>`).join("")}</div>
        </div></div>
        <div class="l-steps">${steps.map(([k, d], i) => `
          <article class="l-step ${i === 0 ? "on" : ""}" data-i="${i}" ${i === 0 ? "" : 'aria-hidden="true"'}>
            <span class="l-step-n"><span class="rule"></span>${t("step", { n: pad2(i + 1) })}</span>
            <h3>${k}</h3><p>${d}</p>
          </article>`).join("")}</div>
      </div>
    </div></div></section>

    <section class="l-stats"><div class="wrap">
      <h2 class="reveal">${pair("l.statsH")}</h2>
      <div class="l-bento">${LANDING_STATS.map((n, i) => `
        <div class="card l-tile t${i} reveal" style="--i:${i}"><span class="dash"></span>
          <b class="num" data-to="${n}">0</b><span>${stats[i]}</span>${i === 5 ? `<span class="l-langs">${LANGS.map((l) => `<span lang="${l.id}">${l.name}</span>`).join("")}</span>` : ""}</div>`).join("")}</div>
    </div></section>

    <section class="l-areas" id="l-areas"><div class="wrap">
      <span class="label reveal">${t("l.nav.areas")}</span>
      <h2 class="reveal" style="--i:1">${pair("l.areasH")}</h2>
      <div class="l-area-row reveal" style="--i:2">${AREA_IDS.map((id, i) => `
        <button type="button" class="l-area ${i === 0 ? "on" : ""}" data-area="${id}">
          ${fig("area-" + id, id)}
          <span class="l-area-text"><b>${areas[id][0]}</b><span>${areas[id][1]}</span></span>
        </button>`).join("")}</div>
    </div></section>

    <section class="l-chat"><div class="wrap l-chat-grid">
      <div>
        <span class="label reveal">${t("l.chatLabel")}</span>
        <h2 class="reveal" style="--i:1">${pair("l.chatH")}</h2>
        <p class="l-sub reveal" style="--i:2">${t("l.chatP")}</p>
        <ul class="l-promises">${t("l.promises").map(([k, d], i) => `
          <li class="reveal" style="--i:${i + 3}"><span class="glyph g-${["si", "ta", "en"][i]}">${[I.check, I.spark, I.chat][i]}</span><div><b>${k}</b><span>${d}</span></div></li>`).join("")}</ul>
      </div>
      <div class="card l-chat-demo reveal" style="--i:2">
        <div class="chat-head"><span class="bot-av">${I.spark}</span>
          <div><b style="font-weight:600">${t("chat.title")}</b><div class="faint">${t("chat.sub")}</div></div></div>
        <div class="l-chat-body">
          <div class="msg user">${t("l.demoQ")}</div>
          <div class="msg bot"><span class="who mono" lang="en">CampusYamu</span>
            <div class="text" lang="en">Yes. Architecture needs a practical aptitude test before selection <span class="cite">S1</span>. Your Z-score is 0.08 above this year's estimated cut-off for your district <span class="cite">S2</span>.</div>
            <div class="sources" lang="en"><span class="chip plain"><b class="mono">S1</b> Handbook · Architecture</span><span class="chip"><b class="mono">S2</b> Your saved search</span></div>
            ${t("enOnly") ? `<div class="faint" style="margin-top:8px">${t("enOnly")}</div>` : ""}
          </div>
        </div>
        <div class="composer"><textarea rows="1" disabled placeholder="${esc(t("ask.ph"))}" aria-label="${esc(t("ask.aria"))}"></textarea><span class="btn" aria-hidden="true">${I.send}</span></div>
      </div>
    </div></section>

    <section class="l-faq" id="l-faq"><div class="wrap">
      <h2 class="reveal">${pair("l.faqH")}</h2>
      <div class="l-faq-list">${t("l.faq").map(([q, a], i) => `
        <details class="reveal" style="--i:${i}" ${i === 0 ? "open" : ""}><summary>${q}<span class="pm" aria-hidden="true"></span></summary><p>${a}</p></details>`).join("")}</div>
    </div></section>

    <div class="wrap">
      <section class="l-final reveal">
        <div><h2>${t("l.ctaH")}</h2><p>${t("l.ctaP")}</p></div>
        <a class="btn mustard" href="#/signin">${t("l.start")} ${I.ne}</a>
      </section>
      <footer class="l-foot">${brand("#/home")}<span class="faint">${t("l.foot")}</span></footer>
    </div>
  </div>`;
  reveal();

  // scroll buttons (the app uses the hash for routing, so these scroll instead of linking)
  $$("[data-scroll]").forEach((b) => b.addEventListener("click", () => $("#" + b.dataset.scroll)?.scrollIntoView({ behavior: REDUCED ? "auto" : "smooth", block: "start" })));

  // "how it works": the section is pinned to the screen while you scroll through it. How far you
  // have scrolled picks the step; the new step slides up into place and the old one slides out above.
  const how = $("#l-how"), stepEls = $$(".l-step"), figEls = $$(".l-stage-fig"), bars = $$(".l-progress i");
  let cur = -1;
  const setStep = (n) => {
    stepEls.forEach((el, i) => {
      el.classList.toggle("on", i === n);
      el.classList.toggle("past", i < n);
      el.toggleAttribute("aria-hidden", i !== n);
    });
    figEls.forEach((el, i) => el.classList.toggle("on", i === n));
  };
  const onScroll = () => {
    if (!how.isConnected) { removeEventListener("scroll", onScroll); removeEventListener("resize", onScroll); return; }
    const r = how.getBoundingClientRect(), total = r.height - innerHeight;
    const x = Math.min(1, Math.max(0, -r.top / total)) * stepEls.length; // 0 … number of steps
    const n = Math.min(stepEls.length - 1, Math.floor(x));
    if (n !== cur) { cur = n; setStep(n); }
    // the current step's bar fills as you scroll through it; earlier bars are full
    bars.forEach((el, i) => {
      el.classList.toggle("done", i < n);
      el.firstElementChild.style.width = i < n ? "100%" : i === n ? `${Math.max(6, Math.min(1, x - n) * 100)}%` : "0";
    });
  };
  addEventListener("scroll", onScroll, { passive: true });
  addEventListener("resize", onScroll);
  onScroll();

  // big numbers count up the first time they come into view
  const statObs = new IntersectionObserver((entries) => entries.forEach((e) => {
    if (!e.isIntersecting) return;
    statObs.unobserve(e.target);
    const el = e.target, to = Number(el.dataset.to);
    if (REDUCED) { el.textContent = to; return; }
    const t0 = performance.now(), dur = 900 + Math.min(700, to * 4);
    const tick = (now) => { const p = Math.min(1, (now - t0) / dur); el.textContent = Math.round(to * (1 - Math.pow(1 - p, 4))); if (p < 1) requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
  }), { threshold: 0.6 });
  $$(".l-tile b[data-to]").forEach((el) => statObs.observe(el));

  // course areas: the card under the pointer (or focused) widens
  const areaEls = $$(".l-area");
  const openArea = (el) => areaEls.forEach((x) => x.classList.toggle("on", x === el));
  areaEls.forEach((el) => { el.addEventListener("mouseenter", () => openArea(el)); el.addEventListener("focus", () => openArea(el)); el.addEventListener("click", () => openArea(el)); });
};

views.signin = async () => {
  app.innerHTML = `
  <div class="wrap"><section class="auth view-enter">
    <div class="auth-top">${brand("#/home")}<div class="nav-right">${themeBtn()}${langMenu()}</div></div>
    <div class="card split">
      <div class="side">
        <span class="label">${t("signin.kicker")}</span>
        <h1 style="margin-top:14px">${esc(t("signin.h1a"))}<br><span class="accent">${esc(t("signin.h1b"))}</span></h1>
        <p class="sub">${t("signin.sub")}</p>
        <form id="signin" novalidate>
          <div class="field"><label for="email">${t("email")}</label><input class="input" id="email" type="email" autocomplete="email" placeholder="you@example.com" value="student@example.com" lang="en"></div>
          <div class="field"><label for="pw">${t("password")}</label><input class="input" id="pw" type="password" autocomplete="current-password" placeholder="••••••••" value="mockpassword"></div>
          <button class="btn block" type="submit">${t("signin.btn")} ${I.ne}</button>
          <div class="divider">${t("or")}</div>
          <button class="btn outline block" type="button" id="create">${t("signin.create")}</button>
          <span class="faint">${t("signin.mock")}</span>
        </form>
      </div>
      <div class="side fig-side">${fig("signin", "Sign-in figure")}</div>
    </div>
  </section></div>`;
  $("#signin").addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = $("#signin .btn[type=submit]");
    btn.disabled = true; btn.textContent = t("signin.busy");
    await sleep(REDUCED ? 0 : 500);
    state.signedIn = true;
    try { sessionStorage.setItem("cy.signed", "1"); } catch {}
    location.hash = "#/form";
  });
  $("#create").addEventListener("click", () => toast(t("signin.supabase")));
};

// ----- results form
views.form = async () => {
  const o = await loadOptions();
  await loadMe().catch(() => {});
  const f = state.form, s = state.step, STEPS = t("steps");
  const saved = await loadReport().catch(() => null);
  const grades = (name, list, value) => `<div class="grades" role="group" aria-label="${esc(t("grade", { name }))}">${list.map((g) =>
    `<button type="button" class="grade" data-name="${esc(name)}" data-g="${g}" aria-pressed="${value === g}">${g}</button>`).join("")}</div>`;
  const stepLabel = (n) => `<span class="label">${t("step", { n: pad2(n) })}</span>`;

  const panels = [
    () => `
      <header>${stepLabel(1)}<h2 style="margin-top:10px">${headline(t("f1.ha"), t("f1.hb"))}</h2>
        <p class="muted">${t("f1.p")}</p></header>
      <div class="field"><span class="flabel">${t("stream")}</span>
        <div class="streams">${o.streams.map((st) => `<button type="button" class="stream" data-stream="${esc(st)}" aria-pressed="${f.stream === st}">${esc(st)}</button>`).join("")}</div></div>
      <div>${f.al.map(([sub, g], i) => `
        <div class="subject">
          <div class="field"><span class="flabel"><span class="mono">${pad2(i + 1)}</span>&nbsp; ${t("al.subject")}</span>
            <select class="select" data-al="${i}">${o.al_subjects.map((x) => `<option ${x === sub ? "selected" : ""}>${esc(x)}</option>`).join("")}</select></div>
          ${grades("al" + i, o.al_grades, g)}
        </div>`).join("")}</div>`,
    () => `
      <header>${stepLabel(2)}<h2 style="margin-top:10px">${headline(t("f2.ha"), t("f2.hb"))}</h2>
        <p class="muted">${t("f2.p")}</p></header>
      <div class="row two">
        <div class="field"><label for="cgt">${t("cgt")}</label><input class="input num" id="cgt" type="number" min="0" max="100" value="${f.cgt}"><span class="hint">${t("cgt.hint")}</span></div>
        <div class="field"><label for="z">${t("z")}</label><input class="input num" id="z" type="number" step="0.0001" value="${esc(f.z_score)}" placeholder="${esc(t("z.ph"))}"><span class="hint">${t("optional")}</span></div>
      </div>
      <div class="zbox" id="zbox"></div>
      <div class="field"><span class="flabel">${t("ol")}</span>
        <div class="row three">${o.ol_subjects.map((sub) => `<div class="field"><span class="hint">${esc(sub)}</span>${grades("ol:" + sub, o.ol_grades, f.ol[sub])}</div>`).join("")}</div></div>`,
    () => `
      <header>${stepLabel(3)}<h2 style="margin-top:10px">${headline(t("f3.ha"), t("f3.hb"))}</h2>
        <p class="muted">${t("f3.p")}</p></header>
      <div class="field"><label for="adm">${t("adm")}</label><select class="select" id="adm">${o.districts.map((d) => `<option ${d === f.admission_district ? "selected" : ""}>${esc(d)}</option>`).join("")}</select></div>
      <div class="row two">
        <div class="field"><label for="hd">${t("hd")}</label><select class="select" id="hd">${o.districts.map((d) => `<option ${d === f.home_district ? "selected" : ""}>${esc(d)}</option>`).join("")}</select></div>
        <div class="field"><label for="ds">${t("ds")}</label><select class="select" id="ds">${(o.ds_divisions[f.home_district] || []).map((d) => `<option ${d === f.ds_division ? "selected" : ""}>${esc(d)}</option>`).join("")}</select></div>
      </div>`,
    () => `
      <header>${stepLabel(4)}<h2 style="margin-top:10px">${headline(t("f4.ha"), t("f4.hb"))}</h2>
        <p class="muted">${t("f4.p")}</p></header>
      <div class="field"><label for="pref">${t("interests")}</label><textarea class="input" id="pref" maxlength="2000" placeholder="${esc(t("pref.ph"))}">${esc(f.preferences)}</textarea></div>
      <div class="interest-tags">${t("tags").map((tag) => `<button type="button" data-tag="${esc(tag)}">+ ${esc(tag)}</button>`).join("")}</div>
      ${o.llm_available ? `<div class="notice">
        <button type="button" class="toggle" role="switch" id="llm" aria-checked="${f.use_llm}" aria-label="${esc(t("llm"))}"></button>
        <div><b style="font-weight:500">${t("llm")}</b><div class="hint">${t("llm.hint")}</div></div>
        <span class="chip" style="margin-left:auto">AI</span></div>` : ""}`,
  ];

  app.innerHTML = shell("form", `
    ${saved && s === 0 ? `<div class="notice reveal"><span class="chip">${t("saved")}</span><span class="muted">${t("saved.p")}</span>
      <a class="btn sm outline" style="margin-left:auto" href="#/results">${t("saved.view")} ${I.ne}</a></div>` : ""}
    <h1 class="reveal" style="--i:1;margin-top:20px">${headline(t("form.ha"), t("form.hb"))}</h1>
    <div class="form-layout">
      <aside><div class="steps">${STEPS.map((label, i) => `<button class="${i === s ? "active" : i < s ? "done" : ""}" data-step="${i}"><span class="mono">${pad2(i + 1)}</span><b>${label}</b></button>`).join("")}</div></aside>
      <form class="card form-panel reveal" style="--i:2" id="form" novalidate>
        ${panels[s]()}
        <div class="form-actions">
          <button type="button" class="btn outline" id="prev" ${s === 0 ? "disabled" : ""}>${I.back} ${t("back")}</button>
          ${s < STEPS.length - 1 ? `<button type="submit" class="btn">${t("continue")}</button>` : `<button type="submit" class="btn">${t("find")} ${I.ne}</button>`}
        </div>
      </form>
    </div>`);
  reveal();

  const rerender = () => views.form();
  $$(".steps button").forEach((b) => b.addEventListener("click", () => { state.step = Number(b.dataset.step); rerender(); }));
  $("#prev").addEventListener("click", () => { state.step--; rerender(); });
  $$(".grade").forEach((b) => b.addEventListener("click", () => {
    const n = b.dataset.name, g = b.dataset.g;
    if (n.startsWith("al")) f.al[Number(n.slice(2))][1] = g; else f.ol[n.slice(3)] = g;
    $$(`.grade[data-name="${CSS.escape(n)}"]`).forEach((x) => x.setAttribute("aria-pressed", x === b));
  }));
  $$(".stream").forEach((b) => b.addEventListener("click", () => {
    f.stream = b.dataset.stream;
    const d = o.stream_hints[f.stream]?.defaults || [];
    if (d.length === 3) f.al = d.map((sub, i) => [sub, f.al[i][1]]);
    rerender();
  }));
  $$("[data-al]").forEach((sel) => sel.addEventListener("change", () => (f.al[Number(sel.dataset.al)][0] = sel.value)));
  $$("[data-tag]").forEach((b) => b.addEventListener("click", () => {
    const ta = $("#pref");
    ta.value = ta.value.trim() ? `${ta.value.trim().replace(/,$/, "")}, ${b.dataset.tag}` : b.dataset.tag;
    f.preferences = ta.value;
  }));
  $("#llm")?.addEventListener("click", (e) => { f.use_llm = !f.use_llm; e.currentTarget.setAttribute("aria-checked", f.use_llm); });
  $("#hd")?.addEventListener("change", (e) => { f.home_district = e.target.value; f.ds_division = (o.ds_divisions[f.home_district] || [])[0]; rerender(); });
  $("#adm")?.addEventListener("change", (e) => (f.admission_district = e.target.value));
  $("#ds")?.addEventListener("change", (e) => (f.ds_division = e.target.value));
  $("#pref")?.addEventListener("input", (e) => (f.preferences = e.target.value));
  $("#cgt")?.addEventListener("input", (e) => (f.cgt = e.target.value));

  const zbox = $("#zbox");
  if (zbox) {
    const draw = () => {
      const z = parseFloat(f.z_score), has = !isNaN(z);
      const p = has ? Math.max(0, Math.min(1, (z + 1) / 4)) : 0;
      const C = Math.PI * 34;
      const hint = !has ? t("z.none", { band: bandLabel("no_history") }) : z >= 2 ? t("z.top") : z >= 1.2 ? t("z.strong") : z >= 0.5 ? t("z.good") : t("z.low");
      zbox.innerHTML = `
        <svg width="92" height="56" viewBox="0 0 92 56" style="flex:none"><path d="M12 50 A34 34 0 0 1 80 50" fill="none" stroke="#fff" stroke-width="8" stroke-linecap="round"/>
          <path d="M12 50 A34 34 0 0 1 80 50" fill="none" stroke="var(--blue)" stroke-width="8" stroke-linecap="round" stroke-dasharray="${C}" stroke-dashoffset="${C * (1 - p)}" style="transition:stroke-dashoffset .7s var(--ease-spring)"/></svg>
        <div><div class="big num">${has ? z.toFixed(4) : "—"}</div>
          <div class="hint" style="margin-top:6px">${hint}</div></div>`;
    };
    draw();
    $("#z").addEventListener("input", (e) => { f.z_score = e.target.value; draw(); });
  }

  $("#form").addEventListener("submit", (e) => {
    e.preventDefault();
    if (s < STEPS.length - 1) { state.step++; rerender(); return; }
    if (new Set(f.al.map((x) => x[0])).size !== 3) { toast(t("err.three")); state.step = 0; rerender(); return; }
    state.pendingRun = api("/v1/recommendations", {
      method: "POST",
      body: {
        stream: f.stream,
        al: f.al.map(([subject, grade]) => ({ subject, grade })),
        ol: Object.entries(f.ol).map(([subject, grade]) => ({ subject, grade })),
        cgt: Number(f.cgt), z_score: f.z_score === "" ? null : Number(f.z_score),
        admission_district: f.admission_district, ds_division: f.ds_division,
        preferences: f.preferences, use_llm: f.use_llm, suggestions: 20,
      },
    });
    location.hash = "#/analysing";
  });
};

// ----- analysing: a live checklist of the five backend steps, next to a figure
views.analysing = async () => {
  if (!state.pendingRun) { location.hash = "#/form"; return; }
  const AGENTS = t("agents");
  app.innerHTML = shell("", `
    <section class="analysing">
      <div class="card split">
        <div class="side">
          <span class="pill live" style="align-self:flex-start"><span class="dot"></span>${t("analysing")}</span>
          <div class="counter num"><span id="cnt">0</span></div>
          <div class="muted">${t("checked")}</div>
          <div class="timeline">${AGENTS.map((a, i) => `<div class="tl-item"><b>${a.k}</b><span class="mono">${pad2(i + 1)} / ${a.d}</span></div>`).join("")}</div>
          <div class="status-line" id="status"></div>
        </div>
        <div class="side fig-side">${fig("analysing", "Analysing figure")}</div>
      </div>
    </section>`);

  let result, error;
  state.pendingRun.then((r) => (result = r)).catch((e) => (error = e));
  const items = $$(".tl-item"), cnt = $("#cnt"), status = $("#status");
  const setStatus = (m) => (status.innerHTML = `<span>${esc(m)}</span>`);
  const total = 126, per = REDUCED ? 50 : 850;

  for (let i = 0; i < AGENTS.length; i++) {
    items[i].className = "tl-item on";
    setStatus(AGENTS[i].msg);
    const c0 = Math.round((total * i) / AGENTS.length), c1 = Math.round((total * (i + 1)) / AGENTS.length);
    const t0 = performance.now();
    await new Promise((res) => {
      const tk = (now) => { const p = Math.min(1, (now - t0) / per); cnt.textContent = Math.round(c0 + (c1 - c0) * p); p < 1 ? requestAnimationFrame(tk) : res(); };
      requestAnimationFrame(tk);
    });
    if (i === AGENTS.length - 1) { while (!result && !error) await sleep(120); } // last step waits for the server
    items[i].className = "tl-item done";
  }
  state.pendingRun = null;
  if (error) { toast(error.message); location.hash = "#/form"; return; }
  state.report = result.report;
  $(".pill.live").innerHTML = `<span class="dot" style="background:var(--blue);animation:none"></span>${t("done")}`;
  setStatus(t("opening"));
  await sleep(REDUCED ? 0 : 600);
  location.hash = "#/results";
};

// ----- results
function courseCard(r, i) {
  const m = r.expected_margin;
  const w = m == null ? 0 : Math.min(1, Math.abs(m));
  const tags = [bandLabel(r.band), r.group === "with_conditions" ? t("conditions") : t("canApply"), r.aptitude_test ? t("aptitude") : null, r.proposed_intake ? t("places", { n: r.proposed_intake }) : null].filter(Boolean);
  return `
  <article class="card course band-${r.band} reveal" style="--i:${i % 6}" data-uni="${esc(r.uni_code)}" tabindex="0" role="link" aria-label="${esc(r.course_name)}, ${esc(r.university)}">
    ${fig("area-" + area(r.course_name), "", { optional: true })}
    <div class="body">
      <div class="meta mono"><span>${esc(r.uni_code)} · ${fmtMin(r.car_min)}</span><span class="idx">${pad2(i + 1)}</span></div>
      <h3 lang="en">${esc(r.course_name)}</h3>
      <div class="uni" lang="en">${esc(r.university)}</div>
      ${m != null ? `<div class="margin">
        <div class="margin-track"><span class="zero"></span><span class="fill ${m < 0 ? "neg" : ""}" data-w="${w}" style="${m < 0 ? "right:50%" : "left:50%"}"></span></div>
        <div class="margin-row"><span>${t("cutoff", { v: r.predicted_cutoff?.toFixed(4) ?? "—" })}</span><span>${t("you")} <b class="num">${m >= 0 ? "+" : ""}${m.toFixed(3)}</b></span></div>
      </div>` : `<div class="margin-row"><span>${r.zscore_note ? `<span lang="en">${esc(r.zscore_note)}</span>` : t("noHistory")}</span></div>`}
      <div class="tags">${tags.map((tag) => `<span>${esc(tag)}</span>`).join("")}</div>
    </div>
  </article>`;
}

views.results = async () => {
  const rep = await loadReport();
  if (!rep) { location.hash = "#/form"; return; }
  await loadMe().catch(() => {});
  const c = rep.counts, p = rep.profile;
  const eligible = (c.can_apply || 0) + (c.with_conditions || 0);
  const banded = BAND_IDS.reduce((sum, id) => sum + (rep.bands[id]?.length || 0), 0) || 1;
  const near = allRows().filter((r) => r.car_min != null && r.car_min <= 45).length;
  if (!rep.bands[state.band]?.length) state.band = BAND_IDS.find((id) => rep.bands[id]?.length) || "strong";
  const year = rep.bands.strong?.[0]?.forecast_year?.replace("_", "/") || "2025/2026";

  app.innerHTML = shell("results", `
    <section class="hero">
      <div>
        <span class="label reveal">${t("intake", { year: esc(year) })}</span>
        <h1 class="reveal" style="--i:1;margin-top:12px">${t("res.ha", { n: `<span class="num" data-count="${eligible}">0</span>` })}<br><span class="accent">${t("res.hb")}</span></h1>
        <div class="slash reveal" style="--i:2" lang="en">
          <span>${esc(p.stream)}</span><span class="sep">/</span>
          <span>${p.al_results.map(([sub, g]) => `${esc(abbrev(sub))} ${g}`).join(" · ")}</span><span class="sep">/</span>
          ${p.z_score != null ? `<span class="accent num">Z ${Number(p.z_score).toFixed(4)}</span><span class="sep">/</span>` : ""}
          <span>${esc(rep.origin?.ds_division || p.home)}, ${esc(p.admission_district)}</span>
        </div>
      </div>
      <div class="reveal" style="--i:3;display:flex;gap:10px;flex-wrap:wrap">
        <a class="btn outline" href="#/form">${t("editResults")}</a>
        <a class="btn" href="#/rankings">${t("nav.order")} ${I.ne}</a>
      </div>
    </section>

    <section class="stats">
      <div class="card stat lead reveal" style="--i:1"><span class="mono">${t("st.strong")}</span><div class="value"><span data-count="${c.band_strong || 0}">0</span><small>${t("of", { n: banded })}</small></div></div>
      <div class="card stat reveal" style="--i:2"><span class="mono">${t("st.comp")}</span><div class="value"><span data-count="${(c.band_competitive || 0) + (c.band_reach || 0)}">0</span></div></div>
      <div class="card stat reveal" style="--i:3"><span class="mono">${t("st.near")}</span><div class="value"><span data-count="${near}">0</span></div></div>
      <div class="card stat warm reveal" style="--i:4"><span class="mono">${t("st.cond")}</span><div class="value"><span data-count="${c.with_conditions || 0}">0</span></div></div>
    </section>

    <section class="card dist reveal">
      <div class="dist-head"><h3>${t("dist.h")}</h3><span class="faint">${t("dist.note", { d: esc(p.admission_district) })}</span></div>
      <div class="dist-bar">${BAND_IDS.map((id) => `<i data-w="${(rep.bands[id]?.length || 0) / banded}" style="background:${BAND_COLOR[id]}" title="${esc(bandLabel(id))}"></i>`).join("")}</div>
      <div class="legend">${BAND_IDS.map((id) => `<span><i style="background:${BAND_COLOR[id]}"></i>${bandLabel(id)} <b class="num">${rep.bands[id]?.length || 0}</b></span>`).join("")}</div>
    </section>

    <section>
      <div class="section-head reveal">
        <h2>${headline(t("all.ha"), t("all.hb"))}</h2>
        <label class="search">${I.search}<input class="input" id="q" placeholder="${esc(t("search"))}" value="${esc(state.query)}"></label>
      </div>
      <div class="tabs" id="bands"><span class="ink"></span>
        ${BAND_IDS.map((id) => `<button class="${state.band === id ? "active" : ""}" data-band="${id}">${bandLabel(id)}<span class="n">${rep.bands[id]?.length || 0}</span></button>`).join("")}
      </div>
      <p class="faint" id="band-desc" style="margin:-8px 0 20px">${t("nearest", { desc: bandDesc(state.band) })}</p>
      <div class="courses" id="courses"></div>
      <div id="more" style="text-align:center;margin-top:24px"></div>
    </section>
    ${rep.notes?.length ? `<footer class="faint" style="margin-top:56px;display:grid;gap:4px" lang="en">${rep.notes.map((n) => `<div>${esc(n)}</div>`).join("")}</footer>` : ""}
  `);
  reveal();
  countUp(app);
  afterPaint(() => { $$(".dist-bar i").forEach((el) => (el.style.width = `${el.dataset.w * 100}%`)); moveInk($("#bands")); });

  const renderCourses = () => {
    const q = state.query.trim().toLowerCase();
    let rows = rep.bands[state.band] || [];
    if (q) rows = allRows().filter((r) => `${r.course_name} ${r.university} ${r.uni_code}`.toLowerCase().includes(q));
    const limit = state.showAll || q ? rows.length : 12;
    $("#courses").innerHTML = rows.length ? rows.slice(0, limit).map(courseCard).join("") : `<div class="card empty">${t("empty")}</div>`;
    $("#more").innerHTML = rows.length > limit ? `<button class="btn outline" id="showall">${t("showAll", { n: rows.length })} ${I.down}</button>` : "";
    $("#showall")?.addEventListener("click", () => { state.showAll = true; renderCourses(); });
    reveal($("#courses"));
    afterPaint(() => $$(".margin-track .fill").forEach((el) => (el.style.transform = `scaleX(${el.dataset.w})`)));
    $$(".course").forEach((el) => {
      const open = () => (location.hash = `#/course/${el.dataset.uni}`);
      el.addEventListener("click", open);
      el.addEventListener("keydown", (e) => e.key === "Enter" && open());
    });
  };
  renderCourses();

  $$("#bands button").forEach((b) => b.addEventListener("click", () => {
    state.band = b.dataset.band; state.showAll = false; state.query = ""; $("#q").value = "";
    $$("#bands button").forEach((x) => x.classList.toggle("active", x === b));
    moveInk($("#bands"));
    $("#band-desc").textContent = t("nearest", { desc: bandDesc(state.band) });
    renderCourses();
  }));
  $("#q").addEventListener("input", (e) => { state.query = e.target.value; renderCourses(); });
};

// ----- rankings: a timeline, like the portfolio's experience section
const RANK_IDS = ["distance", "zscore", "preference"];
views.rankings = async () => {
  const rep = await loadReport();
  if (!rep) { location.hash = "#/form"; return; }
  await loadMe().catch(() => {});
  const fb = rep.rankings.distance?.feedback || {};
  const ranks = t("ranks");
  app.innerHTML = shell("rankings", `
    <section>
      <span class="label reveal">${t("nav.order")}</span>
      <h1 class="reveal" style="--i:1;margin-top:12px">${headline(t("rank.ha"), t("rank.hb"))}</h1>
      <p class="muted reveal" style="--i:2;max-width:620px;margin:16px 0 0;font-size:17px">${t("rank.p", { b: `<b>${esc(ranks.distance)}</b>` })}</p>
    </section>
    <div class="rank-layout">
      <div>
        <div class="tabs reveal" id="rtabs"><span class="ink"></span>${RANK_IDS.map((id) => `<button data-r="${id}" class="${state.ranking === id ? "active" : ""}">${ranks[id]}</button>`).join("")}</div>
        <div class="rank-list" id="rlist"></div>
      </div>
      <aside class="card advice reveal" style="--i:2">
        <span class="chip">${t("advice")}</span>
        <div lang="en">
        <p>${esc(fb.summary || "")}</p>
        ${(fb.priorities || []).map((pr) => `<div class="prio"><b>${esc(pr.label[0].toUpperCase() + pr.label.slice(1))}</b>${esc(pr.advice)}</div>`).join("")}
        </div>
      </aside>
    </div>`);
  reveal();
  afterPaint(() => moveInk($("#rtabs")));

  const list = $("#rlist");
  const notes = rep.rankings.distance?.feedback?.course_notes || {};
  const render = (animate) => {
    const rk = rep.rankings[state.ranking];
    const before = new Map($$(".rank", list).map((el) => [el.dataset.uni, el.getBoundingClientRect()]));
    list.innerHTML = rk.suggestions.slice(0, 10).map((sug, i) => {
      const parts = sug.parts;
      const tot = parts ? Math.abs(parts.interest) + Math.abs(parts.cutoff) + Math.abs(parts.distance) || 1 : 0;
      return `<article class="card rank band-${sug.band} ${animate ? "" : "reveal"}" style="--i:${i}" data-uni="${esc(sug.uni_code)}">
        <div class="pos num">${pad2(sug.position)}</div>
        <div><h3 style="font-size:17px" lang="en">${esc(sug.course_name)}</h3>
          <div class="tags" style="margin-top:3px"><span lang="en">${esc(sug.university)}</span><span>${fmtMin(sug.car_min)}</span><span>${bandLabel(sug.band)}</span></div>
          ${state.ranking === "distance" && notes[sug.uni_code] ? `<div class="note" lang="en">${esc(notes[sug.uni_code].note)}</div>` : ""}</div>
        ${parts ? `<div class="parts"><div class="parts-bar">
            <i data-w="${Math.abs(parts.interest) / tot}" style="background:var(--blue)" title="${esc(t("p.interest"))} ${parts.interest}"></i>
            <i data-w="${Math.abs(parts.cutoff) / tot}" style="background:var(--lav)" title="${esc(t("p.demand"))} ${parts.cutoff}"></i>
            <i data-w="${Math.abs(parts.distance) / tot}" style="background:var(--mustard)" title="${esc(t("p.distance"))} ${parts.distance}"></i></div>
          <div class="parts-legend"><span>${t("p.interest")}</span><span>${t("p.demand")}</span><span>${t("p.distance")}</span></div></div>`
        : `<div class="parts"><div class="margin-row"><span>${t("lastCutoff")}</span><b class="num">${sug.latest_cutoff?.toFixed(4) ?? "—"}</b></div></div>`}
      </article>`;
    }).join("");
    $$(".rank", list).forEach((el) => {
      el.addEventListener("click", () => (location.hash = `#/course/${el.dataset.uni}`));
      if (!animate || REDUCED) return;
      const b = before.get(el.dataset.uni), a = el.getBoundingClientRect();
      if (b) el.animate([{ transform: `translateY(${b.top - a.top}px)` }, { transform: "none" }], { duration: 650, easing: "cubic-bezier(.34,1.2,.64,1)" });
      else el.animate([{ opacity: 0, transform: "translateX(-14px)" }, { opacity: 1, transform: "none" }], { duration: 450, delay: 120, easing: "ease-out", fill: "backwards" });
    });
    if (!animate) reveal(list);
    afterPaint(() => $$(".parts-bar i", list).forEach((el) => (el.style.width = `${el.dataset.w * 100}%`)));
  };
  render(false);
  $$("#rtabs button").forEach((b) => b.addEventListener("click", () => {
    state.ranking = b.dataset.r;
    $$("#rtabs button").forEach((x) => x.classList.toggle("active", x === b));
    moveInk($("#rtabs"));
    render(true);
  }));
};

// ----- course detail + chat
function cutoffChart(r, z) {
  if (r.predicted_cutoff == null || z == null) return `<p class="muted">${t("noChart")}</p>`;
  const vals = [r.predicted_cutoff - r.uncertainty, r.predicted_cutoff + r.uncertainty, r.latest_cutoff, z].filter((v) => v != null);
  const lo = Math.min(...vals) - 0.25, hi = Math.max(...vals) + 0.25;
  const X = (v) => 30 + ((v - lo) / (hi - lo)) * 640;
  const ticks = []; for (let tk = Math.ceil(lo * 4) / 4; tk <= hi; tk += 0.25) ticks.push(tk);
  const bandL = X(r.predicted_cutoff - r.uncertainty), bandR = X(r.predicted_cutoff + r.uncertainty), mid = (bandL + bandR) / 2;
  const youLabel = t("youZ", { v: z.toFixed(2) });
  const youW = Math.max(64, 30 + youLabel.length * 7); // the "You" pill grows with the label
  return `<svg viewBox="0 0 700 150" role="img" aria-label="${esc(t("chart.aria"))}">
    ${ticks.map((tk) => `<line x1="${X(tk)}" x2="${X(tk)}" y1="40" y2="104" stroke="var(--line-soft)"/><text x="${X(tk)}" y="124" text-anchor="middle" font-size="10.5" fill="var(--faint)" font-family="inherit">${tk.toFixed(2)}</text>`).join("")}
    <line x1="30" x2="670" y1="72" y2="72" stroke="var(--line)"/>
    <rect x="${mid}" width="0" y="58" height="28" rx="14" fill="var(--lilac)">
      <animate attributeName="x" from="${mid}" to="${bandL}" dur=".9s" begin=".2s" fill="freeze" calcMode="spline" keySplines=".2 .8 .2 1"/>
      <animate attributeName="width" from="0" to="${bandR - bandL}" dur=".9s" begin=".2s" fill="freeze" calcMode="spline" keySplines=".2 .8 .2 1"/></rect>
    ${r.latest_cutoff != null ? `<circle cx="${X(r.latest_cutoff)}" cy="72" r="5.5" fill="var(--surface)" stroke="var(--ink)" stroke-width="1.3"/>
      <text x="${X(r.latest_cutoff)}" y="99" text-anchor="middle" font-size="11" fill="var(--muted)">${t("lastYear")}</text>` : ""}
    <circle cx="${X(r.predicted_cutoff)}" cy="72" r="5" fill="var(--lav)"/>
    <text x="${X(r.predicted_cutoff)}" y="143" text-anchor="middle" font-size="11" font-weight="600" fill="var(--blue-ink)">${t("estimate", { v: `${r.predicted_cutoff.toFixed(3)} ± ${r.uncertainty.toFixed(3)}` })}</text>
    <g style="transform:translateX(${X(z) - 30}px);transition:transform 1.4s var(--ease) .4s">
      <line x1="30" x2="30" y1="24" y2="100" stroke="var(--blue)" stroke-width="2" stroke-linecap="round"/>
      <rect x="${30 - youW / 2}" y="2" width="${youW}" height="24" rx="12" fill="var(--blue)"/>
      <text x="30" y="18" text-anchor="middle" font-size="11.5" fill="#fff" font-weight="700">${youLabel}</text></g>
  </svg>`;
}
const renderAnswer = (text) => esc(text).replace(/\[([A-Z]\d*)\]/g, '<span class="cite">$1</span>');
const sourcesHtml = (sources) => sources?.length ? `<div class="sources" lang="en">${sources.map((src, i) => `<span class="chip ${src.kind === "career_outlook" ? "" : "plain"}" style="animation:statusIn .4s var(--ease) ${i * 60}ms both"><b class="mono" style="font-size:10px;letter-spacing:0">${esc(src.id)}</b> ${esc(src.citation)}</span>`).join("")}</div>` : "";
// chat answers come from the API in English for now, so they are marked as English text
const botMsg = (m, refused) => `<div class="msg bot ${refused ? "refused" : ""}"><span class="who mono" lang="en">CampusYamu</span><div class="text" lang="en">${renderAnswer(m.content)}</div>${sourcesHtml(m.sources)}</div>`;

views.course = async (uni) => {
  const rep = await loadReport();
  if (!rep) { location.hash = "#/form"; return; }
  await loadMe().catch(() => {});
  const r = findRow(uni);
  if (!r) { location.hash = "#/results"; return; }
  const z = rep.profile.z_score;
  const block = rep.course_details?.[r.course_code]?.blocks?.[r.details_block || 0];
  const u = state.me?.usage?.chat;
  const a = area(r.course_name);

  app.innerHTML = shell("results", `
    <button class="back" id="back">${I.back} ${t("back")}</button>
    <section class="card split detail-hero reveal band-${r.band}">
      <div class="side">
        <div style="display:flex;gap:6px;flex-wrap:wrap">
          <span class="chip ${r.band === "strong" ? "blue" : ""}">${t("chance", { band: bandLabel(r.band) })}</span>
          <span class="chip plain">${esc(r.uni_code)}</span>
          ${r.aptitude_test ? `<span class="chip ink">${t("aptitude")}</span>` : ""}
          ${r.same_district ? `<span class="chip ink">${t("yourDistrict")}</span>` : ""}
        </div>
        <h2 lang="en">${esc(r.course_name)}</h2>
        <div class="muted" style="font-size:14.5px" lang="en">${esc(r.university)}${r.site ? ` · ${esc(r.site)}` : ""}</div>
        <div class="facts">
          <div><span class="mono faint">${t("byCar")}</span><b class="num">${fmtMin(r.car_min)}</b></div>
          <div><span class="mono faint">${t("byBus")}</span><b class="num">${fmtMin(r.bus_min_est)}</b></div>
          <div><span class="mono faint">${t("f.places")}</span><b class="num">${r.proposed_intake ?? "—"}</b></div>
          <div><span class="mono faint">${t("yearsMet")}</span><b class="num">${r.years_met ?? "—"}<span class="faint"> / ${r.years_compared ?? "—"}</span></b></div>
        </div>
      </div>
      <div class="side fig-side">${fig("area-" + a, `Course figure: ${a}`)}</div>
    </section>

    <div class="detail-grid">
      <div style="display:grid;gap:18px">
        <section class="card panel chart reveal" style="--i:1">
          <div class="panel-head"><h3>${t("chart.h")}</h3>
            <span class="mono faint" lang="en">${esc(rep.profile.admission_district)} · ${esc((r.forecast_year || "").replace("_", "/"))}</span></div>
          ${cutoffChart(r, z)}
          ${r.reason ? `<p class="muted" style="font-size:14px;margin:16px 0 0" lang="en">${esc(r.reason)}</p>` : ""}
        </section>
        ${block ? `<section class="card panel reveal" style="--i:2">
          <div class="panel-head"><h3>${t("handbook")}</h3><span class="chip" lang="en">${esc(block.citation)}</span></div>
          ${block.degree_programmes?.length ? `<div class="tags" style="margin-bottom:14px" lang="en">${block.degree_programmes.map((d) => `<span>${esc(d)}</span>`).join("")}</div>` : ""}
          <div class="md" lang="en">${markdown(block.text)}</div></section>` : ""}
      </div>

      <aside class="card chat reveal" style="--i:1">
        <div class="chat-head">
          <span class="bot-av">${I.spark}</span>
          <div style="min-width:0"><b style="font-weight:550">${t("chat.title")}</b><div class="faint" style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${t("chat.sub")}</div></div>
          <button class="icon-btn" id="clear" title="${esc(t("chat.clear"))}" aria-label="${esc(t("chat.clear"))}" style="margin-left:auto">${I.trash}</button></div>
        <div class="chat-body" id="body"></div>
        <div id="research-slot"></div>
        <div class="suggest" id="suggest">${t("suggestions").map((q) => `<button>${esc(q)}</button>`).join("")}</div>
        <form class="composer" id="composer"><textarea id="msg" rows="1" maxlength="1000" placeholder="${esc(t("ask.ph"))}" aria-label="${esc(t("ask.aria"))}"></textarea>
          <button class="btn" aria-label="${esc(t("send"))}">${I.send}</button></form>
        <div class="composer-meta"><span>${t("cites")}</span><span class="num" id="usage">${u ? usageText(u) : ""}</span></div>
      </aside>
    </div>`);
  reveal();
  $("#back").addEventListener("click", () => history.back());

  const body = $("#body");
  const scroll = () => (body.scrollTop = body.scrollHeight);
  const enOnly = t("enOnly");
  const greet = `<div class="msg bot"><span class="who mono" lang="en">CampusYamu</span><div class="text">${t("greet", { course: `<b lang="en">${esc(r.course_name)}</b>`, uni: `<span lang="en">${esc(r.university)}</span>` })}${enOnly ? `<div class="faint" style="margin-top:6px">${enOnly}</div>` : ""}</div></div>`;
  const saved = await api(`/v1/me/chats/${encodeURIComponent(uni)}`).catch(() => ({ messages: [] }));
  body.innerHTML = greet + saved.messages.map((m) => (m.role === "user" ? `<div class="msg user">${esc(m.content)}</div>` : botMsg(m))).join("");
  scroll();

  // career research progress
  let polling = false;
  const showResearch = (career) => {
    const slot = $("#research-slot"), job = career?.job;
    if (!slot || !job) return;
    if (job.state === "running") {
      const p = (job.step + 1) / (job.steps || 6), C = 2 * Math.PI * 9;
      slot.innerHTML = `<div class="research"><svg width="22" height="22" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" fill="none" stroke="var(--lilac)" stroke-width="2.5"/>
        <circle cx="12" cy="12" r="9" fill="none" stroke="var(--blue)" stroke-width="2.5" stroke-linecap="round" stroke-dasharray="${C}" stroke-dashoffset="${C * (1 - p)}" transform="rotate(-90 12 12)" style="transition:stroke-dashoffset .6s var(--ease)"/></svg>
        <div><b style="font-weight:550">${t("researching")}</b><div style="font-size:12.5px" lang="en"><span style="display:inline-block;animation:statusIn .4s var(--ease)">${esc(job.message)}…</span></div></div></div>`;
      if (!polling) {
        polling = true;
        (async () => {
          while ($("#research-slot")) {
            await sleep(2000);
            const next = await api(`/v1/career-outlook?course=${encodeURIComponent(r.course_name)}`).catch(() => null);
            if (!next || !$("#research-slot")) break;
            showResearch(next);
            if (next.job?.state !== "running") break;
          }
          polling = false;
        })();
      }
    } else if (job.state === "done" && career.outlook) {
      slot.innerHTML = `<div class="research">${I.check}<div><b style="font-weight:550">${t("researchReady")}</b> <span class="chip" style="margin-left:4px" lang="en">${esc(career.outlook.overall.label)}</span>
        <div style="font-size:12.5px;margin-top:4px" lang="en">${esc(career.outlook.overall.summary)}</div></div></div>`;
    }
  };
  api(`/v1/career-outlook?course=${encodeURIComponent(r.course_name)}`).then(showResearch).catch(() => {});

  const ta = $("#msg");
  ta.addEventListener("input", () => { ta.style.height = "44px"; ta.style.height = Math.min(120, ta.scrollHeight) + "px"; });
  ta.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("#composer").requestSubmit(); } });

  let busy = false;
  const ask = async (question) => {
    if (busy || !question.trim()) return;
    busy = true; ta.value = ""; ta.style.height = "44px";
    $("#suggest").style.display = "none";
    body.insertAdjacentHTML("beforeend", `<div class="msg user">${esc(question)}</div><div class="msg bot" id="typing"><span class="who mono" lang="en">CampusYamu</span><div class="typing"><i></i><i></i><i></i></div></div>`);
    scroll();
    try {
      const res = await api("/v1/chat", { method: "POST", body: { uni_code: uni, question } });
      $("#typing").remove();
      body.insertAdjacentHTML("beforeend", botMsg({ content: "" }, res.status === "out_of_scope"));
      const msgEl = body.lastElementChild, text = $(".text", msgEl);
      const words = res.answer.split(/(\s+)/);
      let acc = "";
      for (let i = 0; i < words.length; i++) {
        acc += words[i];
        if (i % 2 === 0) { text.innerHTML = renderAnswer(acc); scroll(); if (!REDUCED) await sleep(16); }
      }
      text.innerHTML = renderAnswer(res.answer);
      msgEl.insertAdjacentHTML("beforeend", sourcesHtml(res.sources));
      scroll();
      if (res.usage && state.me) {
        state.me.usage.chat = res.usage;
        $("#usage").textContent = usageText(res.usage);
        const bar = $(".usage");
        if (bar) bar.innerHTML = `<span class="bar"><i style="width:${(res.usage.used / res.usage.limit) * 100}%"></i></span><span class="num">${usageText(res.usage)}</span>`;
      }
      showResearch(res.career);
    } catch (e) {
      $("#typing")?.remove();
      body.insertAdjacentHTML("beforeend", botMsg({ content: e.status === 429 ? e.message : t("chat.err") }, true));
      scroll();
    }
    busy = false;
  };
  $("#composer").addEventListener("submit", (e) => { e.preventDefault(); ask(ta.value); });
  $$("#suggest button").forEach((b) => b.addEventListener("click", () => ask(b.textContent)));
  $("#clear").addEventListener("click", async () => {
    await api(`/v1/me/chats/${encodeURIComponent(uni)}`, { method: "DELETE" }).catch(() => {});
    body.innerHTML = greet; $("#suggest").style.display = ""; toast(t("chat.cleared"));
  });
};

// ----- me / chats
views.me = async () => {
  const me = await loadMe();
  await loadReport().catch(() => {});
  const list = await api("/v1/me/chats").catch(() => []);
  const meter = (label, used, limit, i) => `<div class="card meter reveal" style="--i:${i}"><span class="mono faint">${label}</span>
    <div class="value num">${used}<small> / ${limit}</small></div><div class="track"><i data-w="${used / limit}"></i></div></div>`;
  app.innerHTML = shell("me", `
    <section style="display:flex;align-items:end;gap:20px;flex-wrap:wrap">
      <div><span class="label reveal">${t("account")}</span><h1 class="reveal" lang="en" style="--i:1;margin-top:12px;font-size:clamp(32px,4.4vw,52px)">${esc(me.email.split("@")[0])}<span class="accent">@${esc(me.email.split("@")[1])}</span></h1></div>
      <button class="btn outline reveal" style="--i:2;margin-left:auto" id="signout">${t("signout")}</button>
    </section>
    <h3 style="margin-top:48px">${t("language")}</h3>
    <div class="lang-opts reveal">${LANGS.map((l) => `<button type="button" data-lang="${l.id}" lang="${l.id}" aria-pressed="${l.id === getLang()}"><span class="glyph g-${l.id}">${esc(l.short)}</span>${esc(l.name)}</button>`).join("")}</div>
    <h3 style="margin-top:40px">${t("theme")}</h3>
    <div class="theme-opts reveal">${["system", "light", "dark"].map((v) => `<button type="button" data-theme-opt="${v}" aria-pressed="${v === getTheme()}"><span class="sw sw-${v}" aria-hidden="true"></span>${esc(t("theme." + v))}</button>`).join("")}</div>
    <h3 style="margin-top:40px">${t("todaysUse")}</h3>
    <div class="me-grid">
      ${meter(t("m.chat"), me.usage.chat.used, me.usage.chat.limit, 1)}
      ${meter(t("m.llm"), me.usage.recommendations_llm.used, me.usage.recommendations_llm.limit, 2)}
      ${meter(t("m.research"), me.usage.research.used, me.usage.research.limit, 3)}
    </div>
    <h2 class="reveal" style="margin-bottom:20px">${headline(t("me.ha"), t("me.hb"))}</h2>
    ${list.length ? `<div class="chat-list">${list.map((c, i) => `
      <a class="chat-item reveal" style="--i:${i}" href="#/course/${esc(c.uni_code)}">
        <span class="mono">${pad2(i + 1)}</span>
        <div style="min-width:0;flex:1" lang="en"><b style="font-weight:550">${esc(c.course_name)}</b> <span class="faint">· ${esc(c.university)}</span>
          <div class="faint" style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(c.last || "")}</div></div>
        <span class="chip plain">${t("messages", { n: c.messages })}</span></a>`).join("")}</div>`
      : `<div class="card empty reveal">${fig("empty-chats", "No chats yet figure")}<p style="margin:0">${t("noChats")}</p></div>`}`);
  reveal();
  afterPaint(() => $$(".meter .track i").forEach((el) => (el.style.width = `${el.dataset.w * 100}%`)));
  $("#signout").addEventListener("click", () => {
    state.signedIn = false; try { sessionStorage.removeItem("cy.signed"); } catch {}
    location.hash = "#/home";
  });
};

// ---------------------------------------------------------------- router
async function route() {
  const [, name = "", arg] = location.hash.split("/");
  if (!langChosen && name !== "lang") { location.hash = "#/lang"; return; }
  if (!state.signedIn && !["lang", "home", "signin"].includes(name)) { location.hash = "#/home"; return; }
  if (state.signedIn && name === "home") { location.hash = "#/results"; return; } // signed in: straight to courses
  const view = views[name] || (state.signedIn ? views.results : views.home);
  scrollTo({ top: 0 });
  try { await view(arg && decodeURIComponent(arg)); }
  catch (e) { console.error(e); toast(e.message || t("error")); }
}
addEventListener("hashchange", route);
addEventListener("resize", () => $$(".tabs").forEach(moveInk));
FIGS = await fetch("/figures.json").then((r) => (r.ok ? r.json() : {})).catch(() => ({}));
route();
