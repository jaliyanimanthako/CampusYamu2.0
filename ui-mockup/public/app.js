// CampusYamu UI mockup. Vanilla JS, talks to the /v1 API (mock or live via server.js).
// Visual style follows jaliyanimantha.com: Notion-like, line-art figures, one purple accent.

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const app = $("#app");
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

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

const BANDS = [
  { id: "strong", label: "Strong", desc: "Your Z-score has cleared the cut-off in past years" },
  { id: "competitive", label: "Competitive", desc: "Close to the cut-off: could go either way" },
  { id: "reach", label: "Reach", desc: "Somewhat below recent cut-offs" },
  { id: "unlikely", label: "Unlikely", desc: "Well below recent cut-offs" },
  { id: "no_history", label: "No history", desc: "No past cut-offs to compare" },
];
const BAND_COLOR = { strong: "var(--purple)", competitive: "var(--purple-2)", reach: "var(--purple-3)", unlikely: "color-mix(in srgb, var(--ink) 22%, var(--paper))", no_history: "var(--line)" };

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
  const t = $("#toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.remove("show"), 2800);
}

// ---------------------------------------------------------------- icons
const I = {
  search: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>',
  back: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg>',
  ne: '<svg class="arr" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M7 17L17 7M8 7h9v9"/></svg>',
  down: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M6 13l6 6 6-6"/></svg>',
  send: '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h13M13 6l6 6-6 6"/></svg>',
  check: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>',
  trash: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/></svg>',
  chat: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.4A8 8 0 1 1 21 12z"/></svg>',
  edit: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20h4L19 9l-4-4L4 16z"/></svg>',
  grid: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><rect x="4" y="4" width="7" height="7" rx="2"/><rect x="13" y="4" width="7" height="7" rx="2"/><rect x="4" y="13" width="7" height="7" rx="2"/><rect x="13" y="13" width="7" height="7" rx="2"/></svg>',
  list: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><path d="M9 6h11M9 12h11M9 18h11M4 6h1M4 12h1M4 18h1"/></svg>',
};

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
  if (/medicine|dental|nursing|pharm|health|veterinary|medical|physiotherapy|radiograph|laboratory/.test(n)) return "medicine";
  if (/computer|information|software|data science|ict|artificial/.test(n)) return "it";
  if (/engineer|technology|quantity|architect|design|surveying|town/.test(n)) return "engineering";
  if (/management|commerce|account|business|financ|marketing|tourism|estate|hospitality|logistic/.test(n)) return "management";
  if (/arts|law|language|social|music|dance|drama|media|translation|islamic|buddhist/.test(n)) return "arts";
  return "science";
}

// ---------------------------------------------------------------- helpers
const fmtMin = (m) => (m == null ? "—" : m < 60 ? `${Math.round(m)} min` : `${Math.floor(m / 60)}h ${Math.round(m % 60)}m`);
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
    const tick = (t) => {
      const p = Math.min(1, (t - t0) / dur);
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
  ink.style.width = active.offsetWidth - 24 + "px";
  ink.style.transform = `translateX(${active.offsetLeft + 12}px)`;
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
  return `
  <div class="wrap">
    <header class="topbar"><div class="nav-inner">
      <a class="brand" href="#/results"><i></i>CampusYamu</a>
      <nav class="nav">${link("#/form", "form", "My results")}${link("#/results", "results", "Courses")}${link("#/rankings", "rankings", "Ranked order")}${link("#/me", "me", "Chats")}</nav>
      <div class="nav-right">
        ${u ? `<span class="usage" title="Chat questions used today"><span class="bar"><i style="width:${(u.used / u.limit) * 100}%"></i></span><span class="num">${u.used}/${u.limit} today</span></span>` : ""}
        <a class="avatar" href="#/me" aria-label="Account">S</a>
      </div>
    </div></header>
    <main class="page view-enter">${inner}</main>
  </div>
  <nav class="tabbar" aria-label="Sections">
    <a href="#/form" class="${active === "form" ? "active" : ""}">${I.edit}<span>Results</span></a>
    <a href="#/results" class="${active === "results" ? "active" : ""}">${I.grid}<span>Courses</span></a>
    <a href="#/rankings" class="${active === "rankings" ? "active" : ""}">${I.list}<span>Order</span></a>
    <a href="#/me" class="${active === "me" ? "active" : ""}">${I.chat}<span>Chats</span></a>
  </nav>`;
}
const headline = (plain, accent) => `${esc(plain)} <span class="accent">${esc(accent)}</span>`;

// ---------------------------------------------------------------- views
const views = {};

views.signin = async () => {
  app.innerHTML = `
  <div class="wrap"><section class="auth view-enter">
    <a class="brand"><i></i>CampusYamu</a>
    <div class="card split">
      <span class="node on"></span>
      <div class="side">
        <span class="chip" style="align-self:flex-start">UGC Handbook 2024/25</span>
        <h1 style="margin-top:18px">Find your<br><span class="accent">course.</span></h1>
        <div class="slash"><span>A/L results</span><span class="sep">/</span><span class="accent">university selection</span></div>
        <form id="signin" novalidate>
          <div class="field"><label for="email">Email</label><input class="input" id="email" type="email" autocomplete="email" placeholder="you@example.com" value="student@example.com"></div>
          <div class="field"><label for="pw">Password</label><input class="input" id="pw" type="password" autocomplete="current-password" placeholder="••••••••" value="mockpassword"></div>
          <button class="btn block" type="submit">Sign in ${I.ne}</button>
          <div class="divider">or</div>
          <button class="btn outline block" type="button" id="create">Create an account</button>
          <span class="faint">Mockup: any email and password will do.</span>
        </form>
      </div>
      <div class="side fig-side">${fig("signin", "Sign-in figure")}</div>
    </div>
  </section></div>`;
  $("#signin").addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = $("#signin .btn[type=submit]");
    btn.disabled = true; btn.textContent = "Signing in…";
    await sleep(REDUCED ? 0 : 500);
    state.signedIn = true;
    try { sessionStorage.setItem("cy.signed", "1"); } catch {}
    location.hash = "#/form";
  });
  $("#create").addEventListener("click", () => toast("Sign-up runs through Supabase in the real app"));
};

// ----- results form
const STEPS = ["Stream & subjects", "Scores", "Where you live", "Interests"];
views.form = async () => {
  const o = await loadOptions();
  await loadMe().catch(() => {});
  const f = state.form, s = state.step;
  const saved = await loadReport().catch(() => null);
  const grades = (name, list, value) => `<div class="grades" role="group" aria-label="${esc(name)} grade">${list.map((g) =>
    `<button type="button" class="grade" data-name="${esc(name)}" data-g="${g}" aria-pressed="${value === g}">${g}</button>`).join("")}</div>`;

  const panels = [
    () => `
      <header><span class="label">Step 01</span><h2 style="margin-top:10px">${headline("Stream and", "subjects.")}</h2>
        <p class="muted">Pick your stream and we'll fill in the usual subjects. Change any of them.</p></header>
      <div class="field"><span class="flabel">Stream</span>
        <div class="streams">${o.streams.map((st) => `<button type="button" class="stream" data-stream="${esc(st)}" aria-pressed="${f.stream === st}">${esc(st)}</button>`).join("")}</div></div>
      <div>${f.al.map(([sub, g], i) => `
        <div class="subject">
          <div class="field"><span class="flabel"><span class="mono" style="color:var(--purple)">${pad2(i + 1)}</span>&nbsp; A/L subject</span>
            <select class="select" data-al="${i}">${o.al_subjects.map((x) => `<option ${x === sub ? "selected" : ""}>${esc(x)}</option>`).join("")}</select></div>
          ${grades("al" + i, o.al_grades, g)}
        </div>`).join("")}</div>`,
    () => `
      <header><span class="label">Step 02</span><h2 style="margin-top:10px">${headline("Your", "scores.")}</h2>
        <p class="muted">The Z-score sets your chances. Leave it empty if results aren't out yet.</p></header>
      <div class="row two">
        <div class="field"><label for="cgt">Common General Test mark</label><input class="input num" id="cgt" type="number" min="0" max="100" value="${f.cgt}"><span class="hint">Required, out of 100.</span></div>
        <div class="field"><label for="z">Z-score</label><input class="input num" id="z" type="number" step="0.0001" value="${esc(f.z_score)}" placeholder="e.g. 1.5623"><span class="hint">Optional.</span></div>
      </div>
      <div class="zbox" id="zbox"></div>
      <div class="field"><span class="flabel">O/L grades</span>
        <div class="row three">${o.ol_subjects.map((sub) => `<div class="field"><span class="hint">${esc(sub)}</span>${grades("ol:" + sub, o.ol_grades, f.ol[sub])}</div>`).join("")}</div></div>`,
    () => `
      <header><span class="label">Step 03</span><h2 style="margin-top:10px">${headline("Where you", "live.")}</h2>
        <p class="muted">Your admission district sets the cut-offs. Your home sets travel time.</p></header>
      <div class="field"><label for="adm">Admission district</label><select class="select" id="adm">${o.districts.map((d) => `<option ${d === f.admission_district ? "selected" : ""}>${esc(d)}</option>`).join("")}</select></div>
      <div class="row two">
        <div class="field"><label for="hd">Home district</label><select class="select" id="hd">${o.districts.map((d) => `<option ${d === f.home_district ? "selected" : ""}>${esc(d)}</option>`).join("")}</select></div>
        <div class="field"><label for="ds">DS division</label><select class="select" id="ds">${(o.ds_divisions[f.home_district] || []).map((d) => `<option ${d === f.ds_division ? "selected" : ""}>${esc(d)}</option>`).join("")}</select></div>
      </div>`,
    () => `
      <header><span class="label">Step 04</span><h2 style="margin-top:10px">${headline("What you'd like to", "study.")}</h2>
        <p class="muted">In your own words. It shapes the ranked order, not your eligibility.</p></header>
      <div class="field"><label for="pref">Interests</label><textarea class="input" id="pref" maxlength="2000" placeholder="e.g. engineering, design, working with people">${esc(f.preferences)}</textarea></div>
      <div class="interest-tags">${["medicine", "computing", "law", "management", "architecture", "teaching"].map((t) => `<button type="button" data-tag="${t}">+ ${t}</button>`).join("")}</div>
      ${o.llm_available ? `<div class="notice">
        <button type="button" class="toggle" role="switch" id="llm" aria-checked="${f.use_llm}" aria-label="Read my interests with AI"></button>
        <div><b style="font-weight:500">Read my interests with AI</b><div class="hint">Understands phrasing like "something with animals". Takes 20–40 seconds.</div></div>
        <span class="chip" style="margin-left:auto">AI</span></div>` : ""}`,
  ];

  app.innerHTML = shell("form", `
    ${saved && s === 0 ? `<div class="notice reveal"><span class="chip">Saved</span><span class="muted">You have a saved search from last time.</span>
      <a class="btn sm outline" style="margin-left:auto" href="#/results">View results ${I.ne}</a></div>` : ""}
    <h1 class="reveal" style="--i:1;margin-top:20px">${headline("Your A/L", "results.")}</h1>
    <div class="form-layout">
      <aside><div class="steps">${STEPS.map((t, i) => `<button class="${i === s ? "active" : i < s ? "done" : ""}" data-step="${i}"><span class="mono">${pad2(i + 1)}</span><b>${t}</b></button>`).join("")}</div></aside>
      <form class="card form-panel reveal" style="--i:2" id="form" novalidate>
        ${panels[s]()}
        <div class="form-actions">
          <button type="button" class="btn outline" id="prev" ${s === 0 ? "disabled" : ""}>${I.back} Back</button>
          ${s < STEPS.length - 1 ? `<button type="submit" class="btn">Continue</button>` : `<button type="submit" class="btn">Find my courses ${I.ne}</button>`}
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
    const t = $("#pref");
    t.value = t.value.trim() ? `${t.value.trim().replace(/,$/, "")}, ${b.dataset.tag}` : b.dataset.tag;
    f.preferences = t.value;
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
      zbox.innerHTML = `
        <svg width="92" height="56" viewBox="0 0 92 56" style="flex:none"><path d="M12 50 A34 34 0 0 1 80 50" fill="none" stroke="var(--lavender)" stroke-width="7" stroke-linecap="round"/>
          <path d="M12 50 A34 34 0 0 1 80 50" fill="none" stroke="var(--purple)" stroke-width="7" stroke-linecap="round" stroke-dasharray="${C}" stroke-dashoffset="${C * (1 - p)}" style="transition:stroke-dashoffset .7s var(--ease-spring)"/></svg>
        <div><div class="big num">${has ? z.toFixed(4) : "—"}</div>
          <div class="hint" style="margin-top:6px">${!has ? "No Z-score: every course will show as “no history”." : z >= 2 ? "Top of the range: most courses are open to you." : z >= 1.2 ? "A strong score for most science and management courses." : z >= 0.5 ? "Good for many courses; medicine and engineering will be a reach." : "Focus on courses with lower cut-offs and on your interests."}</div></div>`;
    };
    draw();
    $("#z").addEventListener("input", (e) => { f.z_score = e.target.value; draw(); });
  }

  $("#form").addEventListener("submit", (e) => {
    e.preventDefault();
    if (s < STEPS.length - 1) { state.step++; rerender(); return; }
    if (new Set(f.al.map((x) => x[0])).size !== 3) { toast("Choose three different A/L subjects"); state.step = 0; rerender(); return; }
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
const AGENTS = [
  { k: "Eligibility", d: "subject rules", msg: "Checking your subjects against every course's rules" },
  { k: "Z-score", d: "past cut-offs", msg: "Comparing your Z-score with six years of cut-offs" },
  { k: "Travel", d: "from home", msg: "Measuring the road from your home to each campus" },
  { k: "Interests", d: "what you like", msg: "Matching courses to what you want to study" },
  { k: "Ranking", d: "best order", msg: "Balancing chances, interests and distance" },
];
views.analysing = async () => {
  if (!state.pendingRun) { location.hash = "#/form"; return; }
  app.innerHTML = shell("", `
    <section class="analysing">
      <div class="card split">
        <span class="node on"></span>
        <div class="side">
          <span class="pill live" style="align-self:flex-start"><span class="dot"></span>Analysing</span>
          <div class="counter num"><span id="cnt">0</span></div>
          <div class="muted">courses checked</div>
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
      const tk = (t) => { const p = Math.min(1, (t - t0) / per); cnt.textContent = Math.round(c0 + (c1 - c0) * p); p < 1 ? requestAnimationFrame(tk) : res(); };
      requestAnimationFrame(tk);
    });
    if (i === AGENTS.length - 1) { while (!result && !error) await sleep(120); } // last step waits for the server
    items[i].className = "tl-item done";
  }
  state.pendingRun = null;
  if (error) { toast(error.message); location.hash = "#/form"; return; }
  state.report = result.report;
  $(".pill.live").innerHTML = `<span class="dot" style="background:var(--purple);animation:none"></span>Done`;
  setStatus("Opening your courses…");
  await sleep(REDUCED ? 0 : 600);
  location.hash = "#/results";
};

// ----- results
function courseCard(r, i) {
  const m = r.expected_margin;
  const w = m == null ? 0 : Math.min(1, Math.abs(m));
  const tags = [BANDS.find((b) => b.id === r.band)?.label, r.group === "with_conditions" ? "Conditions" : "Can apply", r.aptitude_test ? "Aptitude test" : null, r.proposed_intake ? `${r.proposed_intake} places` : null].filter(Boolean);
  return `
  <article class="card course band-${r.band} reveal" style="--i:${i % 6}" data-uni="${esc(r.uni_code)}" tabindex="0" role="link" aria-label="${esc(r.course_name)}, ${esc(r.university)}">
    ${fig("area-" + area(r.course_name), "", { optional: true })}
    <div class="body">
      <div class="meta mono"><span>${esc(r.uni_code)} · ${fmtMin(r.car_min)}</span><span class="idx">${pad2(i + 1)}</span></div>
      <h3>${esc(r.course_name)}</h3>
      <div class="uni">${esc(r.university)}</div>
      ${m != null ? `<div class="margin">
        <div class="margin-track"><span class="zero"></span><span class="fill ${m < 0 ? "neg" : ""}" data-w="${w}" style="${m < 0 ? "right:50%" : "left:50%"}"></span></div>
        <div class="margin-row"><span>Cut-off ${r.predicted_cutoff?.toFixed(4) ?? "—"}</span><span>You <b class="num">${m >= 0 ? "+" : ""}${m.toFixed(3)}</b></span></div>
      </div>` : `<div class="margin-row"><span>${esc(r.zscore_note || "No cut-off history to compare")}</span></div>`}
      <div class="tags">${tags.map((t) => `<span>${esc(t)}</span>`).join("")}</div>
    </div>
  </article>`;
}

views.results = async () => {
  const rep = await loadReport();
  if (!rep) { location.hash = "#/form"; return; }
  await loadMe().catch(() => {});
  const c = rep.counts, p = rep.profile;
  const eligible = (c.can_apply || 0) + (c.with_conditions || 0);
  const banded = BANDS.reduce((sum, b) => sum + (rep.bands[b.id]?.length || 0), 0) || 1;
  const near = allRows().filter((r) => r.car_min != null && r.car_min <= 45).length;
  if (!rep.bands[state.band]?.length) state.band = BANDS.find((b) => rep.bands[b.id]?.length)?.id || "strong";

  app.innerHTML = shell("results", `
    <section class="hero">
      <div>
        <span class="label reveal">${esc(rep.bands.strong?.[0]?.forecast_year?.replace("_", "/") || "2025/2026")} intake</span>
        <h1 class="reveal" style="--i:1;margin-top:12px"><span class="num" data-count="${eligible}">0</span> courses<br><span class="accent">you can apply for.</span></h1>
        <div class="slash reveal" style="--i:2">
          <span>${esc(p.stream)}</span><span class="sep">/</span>
          <span>${p.al_results.map(([sub, g]) => `${esc(abbrev(sub))} ${g}`).join(" · ")}</span><span class="sep">/</span>
          ${p.z_score != null ? `<span class="accent num">Z ${Number(p.z_score).toFixed(4)}</span><span class="sep">/</span>` : ""}
          <span>${esc(rep.origin?.ds_division || p.home)}, ${esc(p.admission_district)}</span>
        </div>
      </div>
      <div class="reveal" style="--i:3;display:flex;gap:10px;flex-wrap:wrap">
        <a class="btn outline" href="#/form">Edit results</a>
        <a class="btn" href="#/rankings">Ranked order ${I.ne}</a>
      </div>
    </section>

    <section class="stats">
      <div class="card stat lead reveal" style="--i:1"><span class="mono">Strong chance</span><div class="value"><span data-count="${c.band_strong || 0}">0</span><small>of ${banded}</small></div></div>
      <div class="card stat reveal" style="--i:2"><span class="mono">Competitive or reach</span><div class="value"><span data-count="${(c.band_competitive || 0) + (c.band_reach || 0)}">0</span></div></div>
      <div class="card stat reveal" style="--i:3"><span class="mono">Within 45 min by car</span><div class="value"><span data-count="${near}">0</span></div></div>
      <div class="card stat reveal" style="--i:4"><span class="mono">With conditions</span><div class="value"><span data-count="${c.with_conditions || 0}">0</span></div></div>
    </section>

    <section class="card dist reveal">
      <div class="dist-head"><h3>Chance of admission</h3><span class="faint">From past cut-offs in ${esc(p.admission_district)}. Not a guarantee.</span></div>
      <div class="dist-bar">${BANDS.map((b) => `<i data-w="${(rep.bands[b.id]?.length || 0) / banded}" style="background:${BAND_COLOR[b.id]}" title="${b.label}"></i>`).join("")}</div>
      <div class="legend">${BANDS.map((b) => `<span><i style="background:${BAND_COLOR[b.id]}"></i>${b.label} <b class="num">${rep.bands[b.id]?.length || 0}</b></span>`).join("")}</div>
    </section>

    <section>
      <div class="section-head reveal">
        <h2>${headline("All", "courses.")}</h2>
        <label class="search">${I.search}<input class="input" id="q" placeholder="Search course or university" value="${esc(state.query)}"></label>
      </div>
      <div class="tabs" id="bands"><span class="ink"></span>
        ${BANDS.map((b) => `<button class="${state.band === b.id ? "active" : ""}" data-band="${b.id}">${b.label}<span class="n">${rep.bands[b.id]?.length || 0}</span></button>`).join("")}
      </div>
      <p class="faint" id="band-desc" style="margin:-8px 0 20px">${BANDS.find((b) => b.id === state.band).desc}. Nearest first.</p>
      <div class="courses" id="courses"></div>
      <div id="more" style="text-align:center;margin-top:24px"></div>
    </section>
    ${rep.notes?.length ? `<footer class="faint" style="margin-top:56px;display:grid;gap:4px">${rep.notes.map((n) => `<div>${esc(n)}</div>`).join("")}</footer>` : ""}
  `);
  reveal();
  countUp(app);
  afterPaint(() => { $$(".dist-bar i").forEach((el) => (el.style.width = `${el.dataset.w * 100}%`)); moveInk($("#bands")); });

  const renderCourses = () => {
    const q = state.query.trim().toLowerCase();
    let rows = rep.bands[state.band] || [];
    if (q) rows = allRows().filter((r) => `${r.course_name} ${r.university} ${r.uni_code}`.toLowerCase().includes(q));
    const limit = state.showAll || q ? rows.length : 12;
    $("#courses").innerHTML = rows.length ? rows.slice(0, limit).map(courseCard).join("") : `<div class="card empty">No courses here.</div>`;
    $("#more").innerHTML = rows.length > limit ? `<button class="btn outline" id="showall">Show all ${rows.length} ${I.down}</button>` : "";
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
    $("#band-desc").textContent = BANDS.find((x) => x.id === state.band).desc + ". Nearest first.";
    renderCourses();
  }));
  $("#q").addEventListener("input", (e) => { state.query = e.target.value; renderCourses(); });
};

// ----- rankings: a timeline, like the portfolio's experience section
const RANKS = [
  { id: "distance", label: "Balanced" },
  { id: "zscore", label: "By chance" },
  { id: "preference", label: "By interest" },
];
views.rankings = async () => {
  const rep = await loadReport();
  if (!rep) { location.hash = "#/form"; return; }
  await loadMe().catch(() => {});
  const fb = rep.rankings.distance?.feedback || {};
  app.innerHTML = shell("rankings", `
    <section>
      <span class="label reveal">Ranked order</span>
      <h1 class="reveal" style="--i:1;margin-top:12px">${headline("The order to", "list them.")}</h1>
      <p class="muted reveal" style="--i:2;max-width:620px;margin:16px 0 0;font-size:17px">Three ways to order the same courses. <b>Balanced</b> weighs your interests, how competitive each course is, and how far it is from home.</p>
    </section>
    <div class="rank-layout">
      <div>
        <div class="tabs reveal" id="rtabs"><span class="ink"></span>${RANKS.map((r) => `<button data-r="${r.id}" class="${state.ranking === r.id ? "active" : ""}">${r.label}</button>`).join("")}</div>
        <div class="rank-list" id="rlist"></div>
      </div>
      <aside class="card advice reveal" style="--i:2">
        <span class="chip">Advice</span>
        <p>${esc(fb.summary || "")}</p>
        ${(fb.priorities || []).map((pr) => `<div class="prio"><b>${esc(pr.label[0].toUpperCase() + pr.label.slice(1))}</b>${esc(pr.advice)}</div>`).join("")}
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
        <div><h3 style="font-size:17px">${esc(sug.course_name)}</h3>
          <div class="tags" style="margin-top:3px"><span>${esc(sug.university)}</span><span>${fmtMin(sug.car_min)}</span><span>${BANDS.find((b) => b.id === sug.band)?.label}</span></div>
          ${state.ranking === "distance" && notes[sug.uni_code] ? `<div class="note">${esc(notes[sug.uni_code].note)}</div>` : ""}</div>
        ${parts ? `<div class="parts"><div class="parts-bar">
            <i data-w="${Math.abs(parts.interest) / tot}" style="background:var(--purple)" title="Interest ${parts.interest}"></i>
            <i data-w="${Math.abs(parts.cutoff) / tot}" style="background:var(--purple-3)" title="Demand ${parts.cutoff}"></i>
            <i data-w="${Math.abs(parts.distance) / tot}" style="background:var(--line)" title="Distance ${parts.distance}"></i></div>
          <div class="parts-legend"><span>Interest</span><span>Demand</span><span>Distance</span></div></div>`
        : `<div class="parts"><div class="margin-row"><span>Last cut-off</span><b class="num">${sug.latest_cutoff?.toFixed(4) ?? "—"}</b></div></div>`}
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
  if (r.predicted_cutoff == null || z == null) return `<p class="muted">No cut-off history to chart for this course.</p>`;
  const vals = [r.predicted_cutoff - r.uncertainty, r.predicted_cutoff + r.uncertainty, r.latest_cutoff, z].filter((v) => v != null);
  const lo = Math.min(...vals) - 0.25, hi = Math.max(...vals) + 0.25;
  const X = (v) => 30 + ((v - lo) / (hi - lo)) * 640;
  const ticks = []; for (let t = Math.ceil(lo * 4) / 4; t <= hi; t += 0.25) ticks.push(t);
  const bandL = X(r.predicted_cutoff - r.uncertainty), bandR = X(r.predicted_cutoff + r.uncertainty), mid = (bandL + bandR) / 2;
  return `<svg viewBox="0 0 700 150" role="img" aria-label="Your Z-score compared with the estimated cut-off">
    ${ticks.map((t) => `<line x1="${X(t)}" x2="${X(t)}" y1="40" y2="104" stroke="var(--line-soft)"/><text x="${X(t)}" y="124" text-anchor="middle" font-size="10.5" fill="var(--faint)" font-family="ui-monospace, Menlo, monospace">${t.toFixed(2)}</text>`).join("")}
    <line x1="30" x2="670" y1="72" y2="72" stroke="var(--line)"/>
    <rect x="${mid}" width="0" y="58" height="28" rx="6" fill="var(--lavender)">
      <animate attributeName="x" from="${mid}" to="${bandL}" dur=".9s" begin=".2s" fill="freeze" calcMode="spline" keySplines=".2 .8 .2 1"/>
      <animate attributeName="width" from="0" to="${bandR - bandL}" dur=".9s" begin=".2s" fill="freeze" calcMode="spline" keySplines=".2 .8 .2 1"/></rect>
    ${r.latest_cutoff != null ? `<circle cx="${X(r.latest_cutoff)}" cy="72" r="5.5" fill="var(--surface)" stroke="var(--ink)" stroke-width="1.3"/>
      <text x="${X(r.latest_cutoff)}" y="48" text-anchor="middle" font-size="11" fill="var(--muted)">Last year</text>` : ""}
    <circle cx="${X(r.predicted_cutoff)}" cy="72" r="5" fill="var(--purple-2)"/>
    <text x="${X(r.predicted_cutoff)}" y="143" text-anchor="middle" font-size="11" fill="var(--purple)">Estimate ${r.predicted_cutoff.toFixed(3)} ± ${r.uncertainty.toFixed(3)}</text>
    <g style="transform:translateX(${X(z) - 30}px);transition:transform 1.4s var(--ease) .4s">
      <line x1="30" x2="30" y1="24" y2="100" stroke="var(--purple)" stroke-width="2" stroke-linecap="round"/>
      <rect x="3" y="4" width="54" height="20" rx="4" fill="var(--purple)"/>
      <text x="30" y="18" text-anchor="middle" font-size="11" fill="#fff" font-weight="600">You ${z.toFixed(2)}</text></g>
  </svg>`;
}
const renderAnswer = (text) => esc(text).replace(/\[([A-Z]\d*)\]/g, '<span class="cite">$1</span>');
const sourcesHtml = (sources) => sources?.length ? `<div class="sources">${sources.map((src, i) => `<span class="chip ${src.kind === "career_outlook" ? "" : "plain"}" style="animation:statusIn .4s var(--ease) ${i * 60}ms both"><b class="mono" style="font-size:10px;letter-spacing:0">${esc(src.id)}</b> ${esc(src.citation)}</span>`).join("")}</div>` : "";
const botMsg = (m, refused) => `<div class="msg bot ${refused ? "refused" : ""}"><span class="who mono">CampusYamu</span><div class="text">${renderAnswer(m.content)}</div>${sourcesHtml(m.sources)}</div>`;

views.course = async (uni) => {
  const rep = await loadReport();
  if (!rep) { location.hash = "#/form"; return; }
  await loadMe().catch(() => {});
  const r = findRow(uni);
  if (!r) { location.hash = "#/results"; return; }
  const z = rep.profile.z_score;
  const block = rep.course_details?.[r.course_code]?.blocks?.[r.details_block || 0];
  const band = BANDS.find((b) => b.id === r.band);
  const u = state.me?.usage?.chat;
  const a = area(r.course_name);

  app.innerHTML = shell("results", `
    <button class="back" id="back">${I.back} Back</button>
    <section class="card split detail-hero reveal band-${r.band}">
      <span class="node ${r.band === "strong" ? "on" : ""}"></span>
      <div class="side">
        <div style="display:flex;gap:6px;flex-wrap:wrap">
          <span class="chip">${band.label} chance</span>
          <span class="chip plain">${esc(r.uni_code)}</span>
          ${r.aptitude_test ? `<span class="chip ink">Aptitude test</span>` : ""}
          ${r.same_district ? `<span class="chip ink">Your district</span>` : ""}
        </div>
        <h2>${esc(r.course_name)}</h2>
        <div class="muted" style="font-size:14.5px">${esc(r.university)}${r.site ? ` · ${esc(r.site)}` : ""}</div>
        <div class="facts">
          <div><span class="mono faint">By car</span><b class="num">${fmtMin(r.car_min)}</b></div>
          <div><span class="mono faint">By bus</span><b class="num">${fmtMin(r.bus_min_est)}</b></div>
          <div><span class="mono faint">Places</span><b class="num">${r.proposed_intake ?? "—"}</b></div>
          <div><span class="mono faint">Years met</span><b class="num">${r.years_met ?? "—"}<span class="faint"> / ${r.years_compared ?? "—"}</span></b></div>
        </div>
      </div>
      <div class="side fig-side">${fig("area-" + a, `Course figure: ${a}`)}</div>
    </section>

    <div class="detail-grid">
      <div style="display:grid;gap:18px">
        <section class="card panel chart reveal" style="--i:1">
          <div class="panel-head"><h3>Your Z-score against the cut-off</h3>
            <span class="mono faint">${esc(rep.profile.admission_district)} · ${esc((r.forecast_year || "").replace("_", "/"))}</span></div>
          ${cutoffChart(r, z)}
          ${r.reason ? `<p class="muted" style="font-size:14px;margin:16px 0 0">${esc(r.reason)}</p>` : ""}
        </section>
        ${block ? `<section class="card panel reveal" style="--i:2">
          <div class="panel-head"><h3>From the handbook</h3><span class="chip">${esc(block.citation)}</span></div>
          ${block.degree_programmes?.length ? `<div class="tags" style="margin-bottom:14px">${block.degree_programmes.map((d) => `<span>${esc(d)}</span>`).join("")}</div>` : ""}
          <div class="md">${markdown(block.text)}</div></section>` : ""}
      </div>

      <aside class="card chat reveal" style="--i:1">
        <div class="chat-head">
          <div style="min-width:0"><b style="font-weight:550">Ask about this course</b><div class="faint" style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis">Answers from the handbook and your results</div></div>
          <button class="icon-btn" id="clear" title="Clear this chat" style="margin-left:auto">${I.trash}</button></div>
        <div class="chat-body" id="body"></div>
        <div id="research-slot"></div>
        <div class="suggest" id="suggest">${["What are my chances?", "Is there an aptitude test?", "How far is it from home?", "Research careers for this course"].map((q) => `<button>${q}</button>`).join("")}</div>
        <form class="composer" id="composer"><textarea id="msg" rows="1" maxlength="1000" placeholder="Ask a question…" aria-label="Your question"></textarea>
          <button class="btn" aria-label="Send">${I.send}</button></form>
        <div class="composer-meta"><span>Answers cite their sources</span><span class="num" id="usage">${u ? `${u.used}/${u.limit} today` : ""}</span></div>
      </aside>
    </div>`);
  reveal();
  $("#back").addEventListener("click", () => history.back());

  const body = $("#body");
  const scroll = () => (body.scrollTop = body.scrollHeight);
  const greet = `<div class="msg bot"><span class="who mono">CampusYamu</span><div class="text">Ask me anything about <b>${esc(r.course_name)}</b> at ${esc(r.university)}: entry rules, your chances, the journey, or careers.</div></div>`;
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
      slot.innerHTML = `<div class="research"><svg width="22" height="22" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" fill="none" stroke="var(--lavender)" stroke-width="2.5"/>
        <circle cx="12" cy="12" r="9" fill="none" stroke="var(--purple)" stroke-width="2.5" stroke-linecap="round" stroke-dasharray="${C}" stroke-dashoffset="${C * (1 - p)}" transform="rotate(-90 12 12)" style="transition:stroke-dashoffset .6s var(--ease)"/></svg>
        <div><b style="font-weight:550">Researching careers</b><div style="font-size:12.5px"><span style="display:inline-block;animation:statusIn .4s var(--ease)">${esc(job.message)}…</span></div></div></div>`;
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
      slot.innerHTML = `<div class="research">${I.check}<div><b style="font-weight:550">Career research ready</b> <span class="chip" style="margin-left:4px">${esc(career.outlook.overall.label)}</span>
        <div style="font-size:12.5px;margin-top:4px">${esc(career.outlook.overall.summary)}</div></div></div>`;
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
    body.insertAdjacentHTML("beforeend", `<div class="msg user">${esc(question)}</div><div class="msg bot" id="typing"><span class="who mono">CampusYamu</span><div class="typing"><i></i><i></i><i></i></div></div>`);
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
        $("#usage").textContent = `${res.usage.used}/${res.usage.limit} today`;
        const bar = $(".usage");
        if (bar) bar.innerHTML = `<span class="bar"><i style="width:${(res.usage.used / res.usage.limit) * 100}%"></i></span><span class="num">${res.usage.used}/${res.usage.limit} today</span>`;
      }
      showResearch(res.career);
    } catch (e) {
      $("#typing")?.remove();
      body.insertAdjacentHTML("beforeend", botMsg({ content: e.status === 429 ? e.message : "Something went wrong. Try again." }, true));
      scroll();
    }
    busy = false;
  };
  $("#composer").addEventListener("submit", (e) => { e.preventDefault(); ask(ta.value); });
  $$("#suggest button").forEach((b) => b.addEventListener("click", () => ask(b.textContent)));
  $("#clear").addEventListener("click", async () => {
    await api(`/v1/me/chats/${encodeURIComponent(uni)}`, { method: "DELETE" }).catch(() => {});
    body.innerHTML = greet; $("#suggest").style.display = ""; toast("Chat cleared");
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
      <div><span class="label reveal">Account</span><h1 class="reveal" style="--i:1;margin-top:12px;font-size:clamp(32px,4.4vw,52px)">${esc(me.email.split("@")[0])}<span class="accent">@${esc(me.email.split("@")[1])}</span></h1></div>
      <button class="btn outline reveal" style="--i:2;margin-left:auto" id="signout">Sign out</button>
    </section>
    <h3 style="margin-top:48px">Today's use</h3>
    <div class="me-grid">
      ${meter("Chat questions", me.usage.chat.used, me.usage.chat.limit, 1)}
      ${meter("AI-read searches", me.usage.recommendations_llm.used, me.usage.recommendations_llm.limit, 2)}
      ${meter("Career research", me.usage.research.used, me.usage.research.limit, 3)}
    </div>
    <h2 class="reveal" style="margin-bottom:20px">${headline("Your course", "chats.")}</h2>
    ${list.length ? `<div class="chat-list">${list.map((c, i) => `
      <a class="chat-item reveal" style="--i:${i}" href="#/course/${esc(c.uni_code)}">
        <span class="mono" style="color:var(--purple)">${pad2(i + 1)}</span>
        <div style="min-width:0;flex:1"><b style="font-weight:550">${esc(c.course_name)}</b> <span class="faint">· ${esc(c.university)}</span>
          <div class="faint" style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(c.last || "")}</div></div>
        <span class="chip plain">${c.messages} messages</span></a>`).join("")}</div>`
      : `<div class="card empty reveal">${fig("empty-chats", "No chats yet figure")}<p style="margin:0">No chats yet. Open a course and ask a question.</p></div>`}`);
  reveal();
  afterPaint(() => $$(".meter .track i").forEach((el) => (el.style.width = `${el.dataset.w * 100}%`)));
  $("#signout").addEventListener("click", () => {
    state.signedIn = false; try { sessionStorage.removeItem("cy.signed"); } catch {}
    location.hash = "#/signin";
  });
};

// ---------------------------------------------------------------- router
async function route() {
  const [, name = "", arg] = location.hash.split("/");
  if (!state.signedIn && name !== "signin") { location.hash = "#/signin"; return; }
  const view = views[name] || (state.signedIn ? views.results : views.signin);
  scrollTo({ top: 0 });
  try { await view(arg && decodeURIComponent(arg)); }
  catch (e) { console.error(e); toast(e.message || "Something went wrong"); }
}
addEventListener("hashchange", route);
addEventListener("resize", () => $$(".tabs").forEach(moveInk));
FIGS = await fetch("/figures.json").then((r) => (r.ok ? r.json() : {})).catch(() => ({}));
route();
