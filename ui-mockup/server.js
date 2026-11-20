// CampusYamu UI mockup server: serves the page and a mock /v1 API.
// No dependencies:  node server.js   (or  npm start)
//
// Mock mode (default): /v1 answers come from mock/report.json and canned replies,
// with realistic delays so the loading animations can be seen.
// Live mode: set CAMPUSYAMU_API=http://127.0.0.1:8780 and every /v1 call is forwarded
// to the real FastAPI backend (run it with sign-in off for local testing).

import { createServer } from "node:http";
import { readFile, readdir } from "node:fs/promises";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = fileURLToPath(new URL(".", import.meta.url));
const PUBLIC = join(ROOT, "public");
const PORT = Number(process.env.PORT || 5173);
const LIVE = process.env.CAMPUSYAMU_API?.replace(/\/$/, "");

const report = JSON.parse(await readFile(join(ROOT, "mock/report.json"), "utf8"));

const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json",
  ".svg": "image/svg+xml",
  ".webp": "image/webp",
  ".png": "image/png",
};

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const json = (res, status, body) => {
  res.writeHead(status, { "content-type": "application/json" });
  res.end(JSON.stringify(body));
};
const readBody = async (req) => {
  let data = "";
  for await (const chunk of req) data += chunk;
  return data ? JSON.parse(data) : {};
};

// ---------- mock data ----------
const DISTRICTS = ["Ampara", "Anuradhapura", "Badulla", "Batticaloa", "Colombo", "Galle", "Gampaha",
  "Hambantota", "Jaffna", "Kalutara", "Kandy", "Kegalle", "Kilinochchi", "Kurunegala", "Mannar",
  "Matale", "Matara", "Monaragala", "Mullaitivu", "Nuwara Eliya", "Polonnaruwa", "Puttalam",
  "Ratnapura", "Trincomalee", "Vavuniya"];
const DS = {
  Gampaha: ["Attanagalla", "Biyagama", "Divulapitiya", "Dompe", "Gampaha", "Ja-Ela", "Kelaniya",
    "Mahara", "Minuwangoda", "Mirigama", "Negombo", "Wattala"],
  Colombo: ["Colombo", "Dehiwala", "Homagama", "Kaduwela", "Kesbewa", "Maharagama", "Moratuwa",
    "Ratmalana", "Sri Jayawardanapura Kotte"],
  Kandy: ["Akurana", "Deltota", "Doluwa", "Gangawata Korale", "Harispattuwa", "Kundasale", "Pathadumbara"],
};
const options = {
  streams: ["Arts", "Commerce", "Biological Science", "Physical Science", "Engineering Technology",
    "Biosystems Technology", "Information Communication Technology"],
  stream_hints: {
    "Physical Science": { defaults: ["Combined Mathematics", "Physics", "Chemistry"] },
    "Biological Science": { defaults: ["Biology", "Chemistry", "Physics"] },
    Commerce: { defaults: ["Accounting", "Business Studies", "Economics"] },
    "Engineering Technology": { defaults: ["Engineering Technology", "Science for Technology", "Information & Communication Technology"] },
    "Biosystems Technology": { defaults: ["Biosystems Technology", "Science for Technology", "Agricultural Science"] },
    "Information Communication Technology": { defaults: ["Information & Communication Technology", "Combined Mathematics", "Physics"] },
    Arts: { defaults: [] },
  },
  al_subjects: ["Accounting", "Agricultural Science", "Biology", "Biosystems Technology", "Business Studies",
    "Chemistry", "Combined Mathematics", "Economics", "Engineering Technology", "Geography", "History",
    "Information & Communication Technology", "Physics", "Political Science", "Science for Technology", "Sinhala", "Tamil"],
  al_grades: ["A", "B", "C", "S", "F"],
  ol_subjects: ["Science", "English", "Mathematics"],
  ol_grades: ["A", "B", "C", "S", "W"],
  districts: DISTRICTS,
  ds_divisions: Object.fromEntries(DISTRICTS.map((d) => [d, DS[d] || [d]])),
  llm_available: true,
};

const usage = { chat: { used: 3, limit: 40 }, recommendations_llm: { used: 0, limit: 5 }, research: { used: 1, limit: 3 } };
const chats = new Map(); // uni_code -> [{role, content, sources}]
const jobs = new Map(); // course -> {startedAt}

const allRows = Object.values(report.bands).flat();
const findRow = (uni) => allRows.find((r) => r.uni_code === uni);

const RESEARCH_STEPS = [
  "Planning searches for this course",
  "Reading job boards and industry reports",
  "Scanning student discussions on Reddit",
  "Reading the university's official pages",
  "Collecting specialisations by department",
  "Weighing evidence and writing the outlook",
];

function careerFor(course) {
  const job = jobs.get(course);
  if (!job) return { course, available: true, missing_keys: [], outlook: null, job: null };
  const elapsed = (Date.now() - job.startedAt) / 1000;
  const step = Math.floor(elapsed / 3);
  if (step >= RESEARCH_STEPS.length) {
    return {
      course, available: true, missing_keys: [],
      outlook: {
        generated_at: new Date().toISOString(), status: "success", sources: 27,
        overall: {
          label: "positive", confidence: "medium",
          summary: `Graduates in ${course} are in steady demand across Sri Lanka's private sector, with the strongest openings in Colombo and growing remote work for overseas firms. Starting pay is modest, but rises quickly with experience and professional certification.`,
        },
      },
      job: { course, state: "done", message: "Research complete", started: job.startedAt, finished: Date.now() },
    };
  }
  return {
    course, available: true, missing_keys: [], outlook: null,
    job: { course, state: "running", message: RESEARCH_STEPS[step], step, steps: RESEARCH_STEPS.length, started: job.startedAt },
  };
}

function cannedAnswer(question, row) {
  const q = question.toLowerCase();
  const block = report.course_details[row.course_code]?.blocks?.[row.details_block || 0];
  const s1 = { id: "S1", kind: "course_section", title: row.course_name, citation: block?.citation || "Handbook" };
  const s2 = { id: "S2", kind: "student_report", title: "Your results for this course", citation: "Your saved search" };
  if (/weather|movie|cricket|song|joke/.test(q)) {
    return { answer: "I can only help with this course and the university selection process. Try asking about entry requirements, your chances, or careers.", status: "out_of_scope", sources: [] };
  }
  if (/research|career|job|salary|future|රැකියා|වෘත්තීය|தொழில்|வேலை/.test(q)) {
    const course = row.course_name;
    if (!jobs.has(course)) jobs.set(course, { startedAt: Date.now() });
    return {
      answer: `I've started web research on careers for ${course} at ${row.university}. It reads job boards, student discussions and the university's own pages, so it takes a few minutes. You can keep asking questions while it runs, and later answers will use what it finds.`,
      status: "partly_answered", sources: [s1], career: careerFor(course),
    };
  }
  if (/chance|cut|z-?score|get in|අවස්ථා|කඩඉම|வாய்ப்பு|வெட்டுப்புள்ளி/.test(q)) {
    const m = row.expected_margin;
    const ahead = m != null && m >= 0;
    return {
      answer: row.predicted_cutoff
        ? `This year's cut-off for ${report.profile.admission_district} is estimated at ${row.predicted_cutoff.toFixed(4)} (± ${row.uncertainty?.toFixed(4)}). Your Z-score of ${report.profile.z_score} is ${Math.abs(m).toFixed(4)} ${ahead ? "above" : "below"} that estimate [S2]. In past years your score would have cleared the cut-off in ${row.years_met} of ${row.years_compared} years.\n\n${ahead ? "That puts you in a comfortable position, but cut-offs move every year, so keep a few safer choices too." : "That is ambitious. It is worth listing, but place safer options after it."}`
        : `There is no cut-off history for this course in your district, so I can't estimate your chances from past years [S2].`,
      status: "answered", sources: [s2],
    };
  }
  return {
    answer: `${row.course_name} at ${row.university} is taught at ${row.site || "the main campus"}${row.proposed_intake ? `, with ${row.proposed_intake} places this year` : ""} [S1]. ${row.aptitude_test ? "An aptitude test is required before selection." : "There is no aptitude test for this course."} By car it is about ${Math.round(row.car_min)} minutes from your home in ${report.origin.ds_division} (${Math.round(row.bus_min_est)} by bus) [S2].`,
    status: "answered", sources: [s1, s2],
  };
}

async function mockApi(req, res, url) {
  const p = url.pathname;
  if (p === "/v1/health") return json(res, 200, { ok: true, version: "0.4.0", llm_available: true });
  if (p === "/v1/options") return json(res, 200, options);
  if (p === "/v1/courses") return json(res, 200, [...new Set(allRows.map((r) => r.course_name))].sort());
  if (p === "/v1/me") return json(res, 200, { user_id: "mock-user", email: "student@example.com", usage });
  if (p === "/v1/me/results") return json(res, 200, { request: null, report });
  if (p === "/v1/me/chats") {
    return json(res, 200, [...chats.entries()].map(([uni_code, msgs]) => ({
      uni_code, course_name: findRow(uni_code)?.course_name, university: findRow(uni_code)?.university,
      messages: msgs.length, last: msgs.at(-1)?.content.slice(0, 90),
    })));
  }
  const chatMatch = p.match(/^\/v1\/me\/chats\/([^/]+)$/);
  if (chatMatch) {
    const uni = decodeURIComponent(chatMatch[1]);
    if (req.method === "DELETE") { chats.delete(uni); return json(res, 200, { ok: true }); }
    return json(res, 200, { uni_code: uni, messages: chats.get(uni) || [] });
  }
  if (p === "/v1/recommendations" && req.method === "POST") {
    const body = await readBody(req);
    await sleep(body.use_llm ? 6500 : 4200);
    return json(res, 200, { report, used_llm: !!body.use_llm });
  }
  if (p === "/v1/chat" && req.method === "POST") {
    const body = await readBody(req);
    const row = findRow(body.uni_code || body.course?.uni_code);
    if (!row) return json(res, 400, { detail: "Unknown course" });
    if (usage.chat.used >= usage.chat.limit) return json(res, 429, { detail: "You've used today's chat questions. Come back tomorrow." });
    await sleep(1400 + Math.random() * 1200);
    const out = cannedAnswer(body.question, row);
    usage.chat.used += 1;
    if (out.status !== "out_of_scope") {
      const log = chats.get(row.uni_code) || [];
      log.push({ role: "user", content: body.question }, { role: "assistant", content: out.answer, sources: out.sources });
      chats.set(row.uni_code, log);
    }
    return json(res, 200, { career_research: false, notes: [], model: "mock", career: careerFor(row.course_name), ...out, usage: usage.chat });
  }
  if (p === "/v1/career-outlook") return json(res, 200, careerFor(url.searchParams.get("course")));
  if (p === "/v1/career-outlook/research" && req.method === "POST") {
    const body = await readBody(req);
    jobs.set(body.course, { startedAt: Date.now() });
    usage.research.used += 1;
    return json(res, 200, careerFor(body.course));
  }
  return json(res, 404, { detail: "Not found" });
}

async function proxy(req, res, url) {
  const body = ["GET", "HEAD"].includes(req.method) ? undefined : await (async () => {
    const chunks = []; for await (const c of req) chunks.push(c); return Buffer.concat(chunks);
  })();
  const headers = { "content-type": req.headers["content-type"] || "application/json" };
  if (req.headers.authorization) headers.authorization = req.headers.authorization;
  try {
    const r = await fetch(LIVE + url.pathname + url.search, { method: req.method, headers, body });
    res.writeHead(r.status, { "content-type": r.headers.get("content-type") || "application/json" });
    res.end(Buffer.from(await r.arrayBuffer()));
  } catch (err) {
    json(res, 502, { detail: `Backend not reachable at ${LIVE}: ${err.message}` });
  }
}

async function serveStatic(res, pathname) {
  const rel = normalize(pathname === "/" ? "/index.html" : pathname).replace(/^(\.\.[/\\])+/, "");
  const file = join(PUBLIC, rel);
  if (!file.startsWith(PUBLIC)) return json(res, 403, { detail: "Forbidden" });
  try {
    const data = await readFile(file);
    res.writeHead(200, { "content-type": TYPES[extname(file)] || "application/octet-stream" });
    res.end(data);
  } catch {
    // a missing file with an extension (e.g. a figure not added yet) is a real 404
    if (extname(rel)) return json(res, 404, { detail: "Not found" });
    const data = await readFile(join(PUBLIC, "index.html"));
    res.writeHead(200, { "content-type": TYPES[".html"] });
    res.end(data);
  }
}

createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);
  try {
    if (url.pathname.startsWith("/v1/")) return LIVE ? proxy(req, res, url) : mockApi(req, res, url);
    if (url.pathname === "/figures.json") {
      // which illustrations exist, so the page only requests files that are there
      const files = await readdir(join(PUBLIC, "figures")).catch(() => []);
      const figs = {};
      for (const f of files) {
        const m = f.match(/^(.+)\.(webp|png|svg)$/i);
        if (m && !figs[m[1]]) figs[m[1]] = f;
      }
      return json(res, 200, figs);
    }
    return serveStatic(res, url.pathname);
  } catch (err) {
    console.error(err);
    json(res, 500, { detail: "Mock server error" });
  }
}).listen(PORT, () => {
  console.log(`CampusYamu UI mockup → http://localhost:${PORT}`);
  console.log(LIVE ? `  /v1 forwarded to ${LIVE}` : "  /v1 served from mock data (set CAMPUSYAMU_API to use the real backend)");
});
