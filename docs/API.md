# CampusYamu API: Developer Guide

This guide is for developers building a client (mobile app, web app, or anything else) on the
CampusYamu API. Follow the sections in order the first time through. Later, use them as a reference.

**Contents**

1. [What the API does](#1-what-the-api-does)
2. [Run the API on your machine](#2-run-the-api-on-your-machine)
3. [Connect your app to it](#3-connect-your-app-to-it)
4. [Generate a typed client](#4-generate-a-typed-client-recommended)
5. [The app flow, screen by screen](#5-the-app-flow-screen-by-screen)
6. [Endpoint reference](#6-endpoint-reference)
7. [Errors](#7-errors)
8. [Code examples](#8-code-examples)
9. [Performance and limits](#9-performance-and-limits)
10. [Going to production](#10-going-to-production)
11. [Troubleshooting](#11-troubleshooting)
12. [Versioning](#12-versioning)

---

## 1. What the API does

CampusYamu helps Sri Lankan A/L students choose state-university courses, using the UGC
2024/2025 handbook. A student enters their results and the API returns:

- **Recommendations:** every course they are eligible for, grouped by how likely they are to get
  in (from past Z-score cut-offs), with travel time from home and ranked suggestion lists.
- **Course chat:** answers to questions about one course, with citations to the handbook.
- **Career outlook:** web research on job prospects for a course. It runs in the background and
  is cached.

```
 Mobile app ─┐
             ├──HTTP/JSON──▶  CampusYamu API (FastAPI, port 8780)
 Web app ────┘                   ├─ course finder + Z-score analysis (local data, no internet needed)
                                 ├─ course chat ───────▶ OpenAI (+ Neo4j handbook search, optional)
                                 └─ career research ───▶ OpenAI + Tavily/Firecrawl web search
```

The API is its own service. The project's web page (`make web`, port 8770) is a client of it,
like the mobile app: it calls these same `/v1` endpoints. Its API address is set by `API_BASE_URL`
at the top of the script in `src/campusyamu/web/static/index.html`.

Two pages are always available on a running server:

| URL | What it is |
|---|---|
| `http://<host>:8780/docs` | Interactive docs. You can send real requests from the browser |
| `http://<host>:8780/openapi.json` | The machine-readable contract (OpenAPI 3) |

If this guide and `/openapi.json` ever disagree, `/openapi.json` is correct. Tell the backend owner
so this guide can be fixed.

---

## 2. Run the API on your machine

### 2.1 Prerequisites

| Tool | Version | Check |
|---|---|---|
| git | any | `git --version` |
| Python | 3.11 or newer | `python3 --version` |
| uv (Python package manager) | 0.9 or newer | `uv --version` |
| make | any (preinstalled on macOS/Linux) | `make --version` |
| Docker *(optional, instead of the above)* | 24 or newer | `docker --version` |

Install uv if you don't have it:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh      # macOS / Linux
# Windows (PowerShell): powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2.2 Get the code

```bash
git clone <repository-url> CampusYamu
cd CampusYamu
git checkout <branch you were given>      # e.g. main
```

The data the API needs (knowledge graph, Z-score history, travel times, handbook) is in the
repository under `data/`. You don't need to download anything else.

### 2.3 Install

```bash
make install            # same as: uv sync
```

This creates `.venv/` with every dependency. It takes a minute the first time.

### 2.4 Configure keys

```bash
cp .env.example .env
```

Open `.env` and fill in what you need. **Recommendations work with no keys at all.** Keys only
unlock the AI features:

| Feature | Keys needed in `.env` | Without them |
|---|---|---|
| Recommendations | none | always works |
| AI reading of free-text interests (`use_llm`) | `OPENAI_API_KEY` | keyword matching is used instead |
| Course chat (`/v1/chat`) | `OPENAI_API_KEY` | `/v1/chat` returns `400` |
| Better chat answers (handbook search) | `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` | chat still works, from the course's own handbook section only |
| Career research | `OPENAI_API_KEY`, and `TAVILY_API_KEY` or `FIRECRAWL_API_KEY` | `/v1/career-outlook` reports `available: false` |
| Student sign-in (Supabase Auth) and chat memory | `SUPABASE_URL`, `SUPABASE_DB_URL` (`SUPABASE_JWT_SECRET` only for legacy projects) | the API is open and the chat has no memory (local development only) |
| Allow a browser app on another origin | `API_CORS_ORIGINS` | every origin is allowed (`*`) |

Ask the backend owner for keys. Never commit `.env`.

### 2.5 Start the API

```bash
make api
```

You should see:

```
CampusYamu API docs on http://127.0.0.1:8780/docs
INFO:     Uvicorn running on http://127.0.0.1:8780 (Press CTRL+C to quit)
```

Startup loads the course data and takes a few seconds. Stop the server with `Ctrl+C`.

Useful variations:

```bash
make api API_PORT=9000                                   # another port
uv run python -m campusyamu.api --host 0.0.0.0           # reachable from phones on your Wi-Fi (see 3.1)
uv run python -m campusyamu.api --env-file path/to/.env  # a different env file
```

### 2.6 Check it works

```bash
curl http://127.0.0.1:8780/v1/health
# {"ok":true,"version":"0.4.0","llm_available":true}
```

`llm_available` is `true` only when `OPENAI_API_KEY` is set. Then open
http://127.0.0.1:8780/docs, expand **POST /v1/recommendations**, click **Try it out**, paste the
example from [6.4](#64-post-v1recommendations), and click **Execute**.

### 2.7 Alternative: Docker

```bash
cp .env.example .env            # fill in as in 2.4
docker compose up --build -d    # API on :8780, old web page on :8770
docker compose logs -f api      # follow the API log
docker compose down             # stop
```

---

## 3. Connect your app to it

### 3.1 Base URL

Every path in this guide is relative to a base URL. Which one to use depends on where your app runs:

| Your app runs on | Base URL | Start the server with |
|---|---|---|
| Same computer (browser, desktop, iOS Simulator) | `http://127.0.0.1:8780` | `make api` |
| Android Emulator | `http://10.0.2.2:8780` (the emulator's alias for your computer) | `make api` |
| Physical phone on the same Wi-Fi | `http://<your computer's LAN IP>:8780` | `uv run python -m campusyamu.api --host 0.0.0.0` |
| Production | `https://api.<your-domain>` | see [section 10](#10-going-to-production) |

To find your LAN IP, run `ipconfig getifaddr en0` on macOS, `hostname -I` on Linux, or
`ipconfig` on Windows (look for the IPv4 address). If the phone can't connect, allow incoming
connections on port 8780 in your computer's firewall.

Keep the base URL in one config value (an environment or build flavour) so you can switch
between these.

### 3.2 Plain HTTP during development

Local servers use `http://`, which mobile platforms block by default. Allow it in **debug builds only**:

- **Android:** in a debug-only `res/xml/network_security_config.xml`, allow cleartext traffic for
  `10.0.2.2` and your LAN IP, or set `android:usesCleartextTraffic="true"` in the debug manifest.
- **iOS:** in `Info.plist`, add `NSAppTransportSecurity` → `NSAllowsLocalNetworking = YES`.
- **Flutter / React Native:** apply the Android and iOS settings above to the native projects.

Production uses HTTPS, so release builds need none of this.

### 3.3 Headers

| Header | When |
|---|---|
| `Content-Type: application/json` | every POST |
| `Authorization: Bearer <access token>` | every request except `/v1/health`, when the server has sign-in on (`SUPABASE_URL`). The token is the signed-in student's Supabase access token: sign in with the Supabase SDK (project URL + publishable key from the backend owner) and send `session.access_token`. The SDK refreshes it; on `401`, refresh the session and retry once, or send the student back to sign-in |

### 3.4 Timeouts

Some calls are slow (see [section 9](#9-performance-and-limits)). Set the client timeout to **at
least 90 seconds** for `/v1/chat` and `/v1/recommendations`. Show a loading state while they run.

---

## 4. Generate a typed client (recommended)

You don't have to write request and response classes by hand. Generate them from the running
server's OpenAPI spec:

```bash
# needs Node.js; or use Docker: docker run --rm -v "$PWD:/local" openapitools/openapi-generator-cli generate ...
npx @openapitools/openapi-generator-cli generate \
  -i http://127.0.0.1:8780/openapi.json \
  -g dart-dio \
  -o ./campusyamu_api_client
```

| Platform | Generator (`-g`) |
|---|---|
| Flutter / Dart | `dart-dio` |
| Android (Kotlin) | `kotlin` |
| iOS (Swift) | `swift5` |
| Web / React Native (TypeScript) | `typescript-fetch` or `typescript-axios` |

Regenerate whenever the backend changes. Inside `/v1` the API only *adds* fields (see
[section 12](#12-versioning)), so an older client keeps working.

`report` in the recommendations response is typed as a free-form object because it is large. Its
structure is documented in [6.4](#64-post-v1recommendations). Model the parts you use.

---

## 5. The app flow, screen by screen

```
App start ──▶ GET /v1/options ──▶ Results form ──▶ POST /v1/recommendations ──▶ Course list
                                                                                    │ tap a course
                                                                                    ▼
          GET /v1/career-outlook (poll) ◀── career job started ◀── POST /v1/chat ◀── Course chat
```

**Step 1. App start: load the form values.**
Call `GET /v1/options` once and cache the result for the session. Don't hard-code subject or
district lists: they come from the handbook data and can change. Then call
[`GET /v1/me/results`](#612-get-v1meresults): if the student has searched before (on any device), it
returns the form they sent and the report, so you can fill the form and go straight to the results.
`404` means no search yet.

**Step 2. Results form.** Build it from the options:

| Form field | Source in `/v1/options` | Notes |
|---|---|---|
| Stream | `streams` | When the stream changes, pre-fill A/L subjects from `stream_hints[stream].defaults` |
| 3 × A/L subject + grade | `al_subjects`, `al_grades` | Exactly 3 different subjects |
| O/L Science, English, Maths grades | `ol_subjects`, `ol_grades` | Optional, but needed for courses with O/L requirements |
| Common General Test mark | number 0–100 | **Required.** Below the pass mark, no course is eligible |
| Z-score | number, e.g. `1.5623` | Optional. Without it, every course lands in `no_history` |
| Admission district | `districts` | The district the student sat the exam from (sets the cut-offs) |
| Home DS division | `ds_divisions[<district>]` | Two-step picker: district, then DS division. Used for travel time |
| Interests | free text | e.g. "engineering, design". Optional |
| Use AI for interests | checkbox | Show it only if `llm_available` is `true`. Makes the request slower |

**Step 3. Get recommendations.**
`POST /v1/recommendations`. Show a loading state (a few seconds, or 20–40 s with AI). Keep the
whole `report` in memory, because steps 4–6 use it. The server also saves it as the student's latest
search (replacing the one before), so it comes back after a restart via `GET /v1/me/results`.

**Step 4. Course list.** Show `report.bands` as sections in this order: `strong`,
`competitive`, `reach`, `unlikely`, `no_history`. Optionally add tabs for the three ranked lists
in `report.rankings` (`zscore`, `preference`, `distance`). Each list has a `title` and a
`feedback.summary` you can show as-is.

**Step 5. Course chat.** When a course is tapped, open a chat for that course. Signed in, the simplest
request is `{"uni_code": "008G", "question": "..."}`: the server takes the course row and the student's
facts from their saved search. Or send them yourself:
- `course`: the **whole course row** from `report.bands`, unchanged. If the course also appears
  in `report.rankings.distance.suggestions`, add `order3_position` (its `position`), `parts`, and
  `order3_note` (`report.rankings.distance.feedback.course_notes[uni_code].note`). These are
  optional but improve answers about ranking.
- `student`: built from `report.profile` and `report.origin` (see [6.5](#65-post-v1chat)).
- `history`: not needed when the student is signed in: **the server keeps every course chat** (one per
  student per course) and remembers it. When the chat screen opens, show the saved messages from
  [`GET /v1/me/chats/{uni_code}`](#610-get-v1mechatsuni_code). Only a server with sign-in off (local
  development) needs the earlier turns in `history`.
- After each answer, `usage` says how many chat questions the student has used today; show it near
  the input if you like. Past the daily limit the API returns `429` with a message to show.

**Step 6. Career research.** If a chat reply has `career.job.state == "running"`, or after
you call `POST /v1/career-outlook/research`, poll `GET /v1/career-outlook?course=<course_name>`
every 5 seconds and show `job.message` as progress. Stop when the state is `done` or `failed`.
After `done`, later chat answers about careers use the research automatically.

---

## 6. Endpoint reference

Base path: `/v1`. All bodies are JSON.

| # | Method | Path | Auth | Typical time |
|---|---|---|---|---|
| 6.1 | GET | `/v1/health` | none | instant |
| 6.2 | GET | `/v1/options` | sign-in* | instant |
| 6.3 | GET | `/v1/courses` | sign-in* | instant |
| 6.4 | POST | `/v1/recommendations` | sign-in* | 1–5 s; 20–40 s with `use_llm` |
| 6.5 | POST | `/v1/chat` | sign-in* | 5–20 s |
| 6.6 | GET | `/v1/career-outlook` | sign-in* | instant |
| 6.7 | POST | `/v1/career-outlook/research` | sign-in* | instant (the job then runs 3–10 min) |
| 6.8 | GET | `/v1/me` | sign-in | instant |
| 6.9 | GET | `/v1/me/chats` | sign-in | instant |
| 6.10 | GET | `/v1/me/chats/{uni_code}` | sign-in | instant |
| 6.11 | DELETE | `/v1/me/chats/{uni_code}` | sign-in | instant |
| 6.12 | GET | `/v1/me/results` | sign-in | instant |

\* `Authorization: Bearer <token>` of a signed-in student, when the server has sign-in on (`SUPABASE_URL`).
The `/v1/me` endpoints always need sign-in (`400` on a server without it).

**Sign-in and sign-up** happen in the Supabase SDK, not in this API: `signUp({email, password})` and
`signInWithPassword({email, password})` (more methods, such as phone codes or Google, can be switched on in
Supabase later). Ask the backend owner for the project URL and the publishable key.

**Daily limits** per student on the paid calls (Sri Lanka days; numbers in `config/settings.yaml`
`limits`): chat questions, recommendations with `use_llm`, and research runs. Only successful calls
count. Past a limit the API answers `429` with a message to show; `GET /v1/me` gives today's counts.

### 6.1 `GET /v1/health`

Use this to check the server is up and whether AI features are on.

```json
{"ok": true, "version": "0.4.0", "llm_available": true}
```

| Field | Type | Meaning |
|---|---|---|
| `ok` | bool | Server finished starting up |
| `version` | string | Backend version |
| `llm_available` | bool | OpenAI is configured: `use_llm` and `/v1/chat` will work |

### 6.2 `GET /v1/options`

The values for the results form.

```json
{
  "streams": ["Arts", "Commerce", "Biological Science", "Physical Science", "Engineering Technology",
              "Biosystems Technology", "Information Communication Technology"],
  "stream_hints": {
    "Biological Science": {"defaults": ["Biology", "Chemistry", "Physics"],
                           "allowed": ["Biology", "Chemistry", "Physics", "Agricultural Science"],
                           "source": "owner stream_subjects"},
    "Commerce": {"defaults": ["Accounting", "Business Studies", "Economics"],
                 "required_any": ["Accounting", "Business Studies", "Economics"], "source": "form hint"},
    "Engineering Technology": {"defaults": ["Engineering Technology", "Science for Technology",
                                            "Information & Communication Technology"],
                               "required_all": ["Engineering Technology", "Science for Technology"],
                               "source": "form hint"},
    "Arts": {"defaults": [], "source": "form hint"}
  },
  "al_subjects": ["Accounting", "Agricultural Science", "Agro Technology", "Arabic", "..."],
  "al_grades": ["A", "B", "C", "S", "F"],
  "ol_subjects": ["Science", "English", "Mathematics"],
  "ol_grades": ["A", "B", "C", "S", "W"],
  "districts": ["Ampara", "Anuradhapura", "...", "Vavuniya"],
  "ds_divisions": {"Kandy": ["Akurana", "Deltota", "Doluwa", "...", "Gangawata Korale", "..."], "...": []},
  "llm_available": true
}
```

| Field | Meaning |
|---|---|
| `streams` | A/L streams |
| `stream_hints[stream].defaults` | Subjects to pre-fill when the stream is picked (may be empty) |
| `stream_hints[stream].allowed` | *(some streams)* Subjects that normally belong to the stream |
| `stream_hints[stream].required_any` | *(some streams)* At least one of these is usual |
| `stream_hints[stream].required_all` | *(some streams)* All of these are usual |
| `al_subjects` | Every A/L subject (54) |
| `al_grades` / `ol_grades` | Allowed grades |
| `ol_subjects` | The O/L subjects the form asks about |
| `districts` | 25 districts (for both admission district and home district) |
| `ds_divisions` | District → its DS divisions (339 in total) |
| `llm_available` | Same as in `/v1/health` |

Stream hints are for **form help only**: pre-filling, and a soft "this doesn't look like a
normal combination" warning. Don't block submission with them. The server decides eligibility
from the subjects themselves.

### 6.3 `GET /v1/courses`

Every course name, sorted: `["Accounting Information Systems", "Agribusiness Management", ...]`.
Use these exact names for `/v1/career-outlook`.

### 6.4 `POST /v1/recommendations`

Runs the full analysis for one student.

**Request**

```json
{
  "stream": "Physical Science",
  "al": [{"subject": "Combined Mathematics", "grade": "A"},
         {"subject": "Physics", "grade": "B"},
         {"subject": "Chemistry", "grade": "C"}],
  "ol": [{"subject": "Science", "grade": "B"},
         {"subject": "English", "grade": "B"},
         {"subject": "Mathematics", "grade": "A"}],
  "cgt": 40,
  "z_score": 1.56,
  "admission_district": "Kandy",
  "ds_division": "Gangawata Korale",
  "preferences": "engineering, design",
  "use_llm": false,
  "suggestions": 20
}
```

| Field | Type | Required | Rules |
|---|---|---|---|
| `stream` | string | yes | one of `streams` |
| `al` | list of `{subject, grade}` | yes | exactly 3, all different subjects, from `al_subjects` / `al_grades` |
| `ol` | list of `{subject, grade}` | no | from `ol_subjects` / `ol_grades`. An entry with `grade: ""` is ignored |
| `cgt` | integer 0–100 | yes | Common General Test mark |
| `z_score` | number or `null` | no | e.g. `1.5623`. `null` means no Z-score analysis |
| `admission_district` | string | yes | one of `districts` |
| `ds_division` | string | yes | one of `ds_divisions[<home district>]` |
| `preferences` | string | no | free text, max 2000 characters |
| `use_llm` | bool | no (default `false`) | use AI to read `preferences`. Ignored if `llm_available` is false |
| `suggestions` | integer 5–50 | no (default `20`) | entries in each ranked list |

**Response `200`**

```json
{"report": { ... }, "used_llm": false}
```

`used_llm` tells you whether AI was actually used. It is false if you asked for it but the server
has no OpenAI key.

**The `report` object**

| Key | What it holds |
|---|---|
| `profile` | The student's inputs as the server understood them: `stream`, `al_results`, `common_general_test`, `admission_district`, `home`, `ol_results`, `z_score` |
| `origin` | Home location: `ds_division`, `district`, `province`, `origin_id` |
| `counts` | Totals: `can_apply`, `with_conditions`, `not_eligible`, `band_strong`, `band_competitive`, ... |
| `bands` | **The main result**: eligible courses by chance of admission (see below) |
| `rankings` | Three ranked suggestion lists: `zscore`, `preference`, `distance` (see below) |
| `preferences` | How the free-text interests were read, matched courses per interest, `best_overall` |
| `course_details` | Handbook facts per course code, for course detail screens (see below) |
| `notes` | List of strings to show as footnotes, e.g. how travel time is estimated |

**`report.bands`**: an object with five lists of course rows, best first:

| Band | Meaning |
|---|---|
| `strong` | The student's Z-score has cleared this course's cut-off in past years |
| `competitive` | Close to the cut-off: could go either way |
| `reach` | Somewhat below recent cut-offs |
| `unlikely` | Well below recent cut-offs |
| `no_history` | No cut-off history to compare (or no Z-score given). Eligible, but the chance is unknown |

Within each band, courses are sorted by travel time from home, nearest first.

**Course row**: each entry in a band. The fields you'll use most:

| Field | Example | Meaning |
|---|---|---|
| `uni_code` | `"013B"` | **Unique ID** of this course at this university. Use it as the list key |
| `course_code` | `"013"` | Course code (same for every university offering it) |
| `course_name` | `"Physical Science"` | |
| `university` | `"University of Peradeniya"` | |
| `site`, `site_district` | `"Peradeniya ..."`, `"Kandy"` | Where it is taught |
| `band` | `"strong"` | as above |
| `group` | `"can_apply"` | `can_apply` = all requirements met. `with_conditions` = extra conditions apply (aptitude test, O/L to confirm, ...) |
| `aptitude_test` | `false` | An aptitude test is required |
| `ol_met`, `ol_failed`, `ol_unknown` | lists | O/L requirements met, failed, or not checkable from the input |
| `proposed_intake` | `280` | Places offered |
| `latest_cutoff`, `latest_year` | `1.2874`, `"2024_2025"` | Last year's cut-off for the admission district |
| `predicted_cutoff`, `uncertainty` | `1.2678`, `0.1088` | Estimated cut-off for this year, ± uncertainty |
| `expected_margin` | `0.2922` | Student's Z-score minus the predicted cut-off (positive is good) |
| `years_met`, `years_compared` | `6`, `6` | Past years in which the student's score would have cleared the cut-off |
| `reason` | text | One-paragraph explanation of the band. Show it on the detail screen |
| `car_min`, `bus_min_est`, `road_km` | `8.2`, `27.0`, `6.99` | Travel time by car (minutes), rough bus estimate, road distance from home |
| `same_district` | `true` | The site is in the student's home district |
| `preference_score` | `-2` | How well the course matches the stated interests (higher is better) |
| `details_block` | `0` | Index into `course_details[course_code].blocks` for this row |

Some fields are missing or `null` when they don't apply. For example, `no_history` rows have no
cut-off fields and usually carry a `zscore_note` that explains why. Treat every field except `uni_code`,
`course_code`, `course_name`, `university` and `band` as optional.

**`report.rankings`**: three lists that answer "which order should I put my choices in?":

| Key | Ordered by |
|---|---|
| `zscore` | Chance of admission |
| `preference` | Interest match combined with how competitive the course is |
| `distance` | Interests, competitiveness, and closeness to home, balanced. **This is the main one** |

Each ranking has `title` (show it as the heading), `total`, `suggestions` (list), and `notes`.
Each suggestion has `position`, `uni_code`, `course_code`, `course_name`, `university`, `band`,
`latest_cutoff`, `car_min`, `preference_score`, `flags` (e.g. `["aptitude test"]`), and for
`preference`/`distance` a `combined_score`. `distance` suggestions also have
`parts: {interest, cutoff, distance}`, which shows how the score is made up and works well as a
small bar chart.

`rankings.distance` also has:
- `feedback.summary`: a paragraph of advice about the list. Show it above the list.
- `feedback.course_notes[uni_code].note`: one sentence per course explaining its position.
- `feedback.close_calls[]`: `{ranks, note}` pairs that are nearly tied.
- `feedback.priorities[]`: `{label, advice}`, i.e. "if being close to home matters more ...".
- `analysis`: the raw sensitivity analysis behind the feedback (optional to use).

**`report.course_details`**: handbook facts, keyed by `course_code`:

```json
"013": {
  "course_name": "Physical Science",
  "blocks": [{
    "title": "Physical Science",
    "section": "2.2.4.5",
    "pages": [78],
    "citation": "Handbook §2.2.4.5, p. 78",
    "degree_programmes": ["Bachelor of Science in Physical Science"],
    "duration": [], "medium": [], "notes": [], "specializations": {},
    "text": "##### 2.2.4.5 Physical Science\n\n**(Course Code - 013)** ..."
  }]
}
```

For a course row, the matching block is `course_details[row.course_code].blocks[row.details_block]`.
`text` is the handbook section in Markdown: render it with a Markdown widget, or show
`degree_programmes`, `duration` and `medium` as plain facts.

**Errors:** `400` with a message you can show the user (e.g. `"Choose three different A/L
subjects"`, `"Please fill in: three A/L subjects"`). `422` if a field is missing or the wrong type.

### 6.5 `POST /v1/chat`

Answers one question about one course. Needs `llm_available: true`.

**Request**

```json
{
  "question": "What are the career prospects?",
  "course": {
    "uni_code": "025A", "course_code": "025", "course_name": "Law",
    "university": "University of Colombo", "band": "unlikely", "latest_cutoff": 1.9568,
    "car_min": 118.4, "...": "all other fields of the course row, unchanged"
  },
  "student": {
    "stream": "Arts",
    "al_results": [["Political Science", "A"], ["History", "B"], ["Sinhala", "A"]],
    "z_score": 1.56,
    "admission_district": "Kandy",
    "home": "Gangawata Korale (Kandy)",
    "interests": "law, debating"
  },
  "history": [
    {"role": "user", "content": "Is there an aptitude test?"},
    {"role": "assistant", "content": "Yes. ..."}
  ]
}
```

| Field | Required | How to fill it |
|---|---|---|
| `question` | yes | The student's message, 1–1000 characters |
| `course` | one of the two | The course row from `report.bands`. Must include `course_code`. Send the whole row: every field is used as context |
| `uni_code` | one of the two | Signed in only: the course's UNI code from the student's saved search (6.12). The server fills in `course` and, when `student` is missing, `student` |
| `student` | no | `stream`, `al_results`, `z_score`, `admission_district` from `report.profile`; `home` as `"<origin.ds_division> (<origin.district>)"`; `interests` from `report.preferences.text` |
| `history` | no | Earlier turns of **this course's** chat, oldest first, `role` = `user` or `assistant`. Leave out failed or error messages. At most 40 turns of up to 4,000 characters each (otherwise 422); the server uses the last 8 |

**Response `200`**

```json
{
  "answer": "Law graduates in Sri Lanka typically ... [S1] [C]",
  "status": "answered",
  "sources": [
    {"id": "S1", "kind": "course_section", "title": "Law", "citation": "Handbook §2.2.8.10, p. 98–100"},
    {"id": "C", "kind": "career_outlook", "title": "Career research: Law (Sri Lanka)",
     "citation": "web research, 2026-11-13",
     "links": [{"id": "E001", "title": "...", "url": "https://..."}]}
  ],
  "career_research": true,
  "notes": [],
  "model": "gpt-4o-mini",
  "career": {"course": "Law", "available": true, "missing_keys": [], "outlook": {"...": "..."}, "job": null}
}
```

| Field | Meaning |
|---|---|
| `answer` | Plain text (keep line breaks). It may contain source tags like `[S1]` that refer to `sources[].id` |
| `status` | `answered`, `partly_answered`, `not_in_sources` (the handbook doesn't cover it: you might show a hint), or `out_of_scope`: the question was outside the chat's domain (only this course and the university selection process) and `answer` is a fixed refusal. Refused questions are not saved to the chat and count toward the daily limit |
| `sources` | Citations actually used. Show them under the answer: `citation`, plus `title`, plus `links` as tappable URLs |
| `career_research` | A cached career outlook was used for this answer |
| `website_research` | The university website research (sources `W` / `D`) was used for this answer |
| `notes` | Small status messages for the user (e.g. "handbook search unavailable") |
| `career` | Career-research status for this course, same shape as [6.6](#66-get-v1career-outlook). If `career.job.state` is `"running"`, start polling |

Source kinds:

| `kind` | Is |
|---|---|
| `course_section` | This course's section of the handbook |
| `student_report` | The student's own results for this course |
| `handbook_search` | Another handbook passage found by search (general rules, applications, ...) |
| `career_outlook` | The cached web career research (has `links`) |
| `university_website` | What the university's official website says about the course: overview, faculty, modules, specialisations, training, … (has `links` to the pages) |
| `specialisations` | One card per specialisation from its department's page (has `links`) |

If the student asks for research in the chat ("research this course", "look up its modules", "research careers"), the server starts it in the background: career trends (web + Reddit), the university's official website, and its specialisations, all in parallel, for this course at this university. `career.job.state` becomes `"running"` and `career.job.scope` is `"course"`; poll [6.6](#66-get-v1career-outlook) as for career research. When it is done, later answers use the new `W` and `D` sources. Send the whole course row as `course` (with `uni_code` and `university`) so the right university is researched.

**Errors:** `400` if the server has no OpenAI key or `course.course_code` is missing. `502` if
OpenAI failed: show "try again".

### 6.6 `GET /v1/career-outlook`

`GET /v1/career-outlook?course=Law` (the course name, URL-encoded). Returns the cached career
outlook and the research-job status.

```json
{
  "course": "Law",
  "available": true,
  "missing_keys": [],
  "outlook": {
    "generated_at": "2026-11-13T09:40:22.800046+00:00",
    "status": "success",
    "sources": 29,
    "overall": {
      "label": "positive",
      "summary": "Prospects for law graduates in Sri Lanka are encouraging ...",
      "confidence": "medium",
      "evidence_refs": ["E001", "E019", "E024"]
    }
  },
  "job": null
}
```

| Field | Meaning |
|---|---|
| `available` | The server can run career research. If false, hide the "Research careers" button |
| `missing_keys` | Which server keys are missing (for the backend owner, not the student) |
| `outlook` | `null` if research has never run for this course. Otherwise a summary: `overall.label` (e.g. `positive`), `overall.summary` (show it), `overall.confidence`, `sources` (number of web sources) |
| `job` | `null` if no job has run since the server started. Otherwise `{course, state, message, started, finished}` |

`job.state` is `running` (show `job.message` as progress), `done` (refresh: `outlook` is now
filled), or `failed` (show `job.message`, and offer retry).

The full outlook (SWOT, evidence) isn't returned here. It is used by `/v1/chat`, so to show more
detail, ask the chat (e.g. "What does the career research say?").

### 6.7 `POST /v1/career-outlook/research`

Starts career research for one course in the background. It calls paid web-search and OpenAI APIs,
so only call it when the student taps an explicit button.

**Request:** `{"course": "Law"}`. Use an exact name from `/v1/courses` (or a row's `course_name`).

| Status | Meaning | Body |
|---|---|---|
| `202` | Started. Poll [6.6](#66-get-v1career-outlook) | same as 6.6, plus `message: "started"` |
| `409` | Another course is being researched (one at a time). Try again later | same as 6.6, plus `message` explaining |
| `400` | Unknown course, or research keys missing on the server | `{"errors": [...]}` |
| `429` | The student's daily research limit is reached | `{"errors": [...]}` |

### 6.8 `GET /v1/me`

The signed-in student and today's use of the paid calls.

```json
{"user_id": "3f2a9c1e-...", "usage": {"chat": {"used": 12, "limit": 60},
 "ai_recommendations": {"used": 1, "limit": 10}, "research": {"used": 0, "limit": 3}}}
```

`limit: 0` means no limit.

### 6.9 `GET /v1/me/chats`

The student's course chats, most recent first (for a "My chats" screen).

```json
[{"uni_code": "023G", "course_code": "023", "course_name": "Architecture",
  "university": "University of Moratuwa", "messages": 14,
  "created_at": "2026-11-14T06:20:00+00:00", "updated_at": "2026-11-14T07:02:11+00:00"}]
```

### 6.10 `GET /v1/me/chats/{uni_code}`

One course chat's saved messages, **oldest first**: show them when the chat screen opens.
Query: `limit` (default 50, at most 200) and `before` (a `seq`) to page back.

```json
{"uni_code": "023G", "course_code": "023", "course_name": "Architecture", "university": "University of Moratuwa",
 "messages": [
   {"seq": 13, "role": "user", "content": "Is there an aptitude test?", "sources": [],
    "created_at": "2026-11-14T07:02:01+00:00"},
   {"seq": 14, "role": "assistant", "content": "Yes, ... [S1]", "sources": [{"id": "S1", "kind": "course_section", "...": "..."}],
    "created_at": "2026-11-14T07:02:11+00:00"}],
 "has_more": true}
```

`has_more: true` means older messages exist: call again with `before=<the first message's seq>`.
`404` when the student has no chat for that course yet (show the empty chat).

### 6.11 `DELETE /v1/me/chats/{uni_code}`

Deletes one course chat for good (messages and its summary). What CampusYamu learned about the
student (their facts) stays. Ask the student to confirm first. Returns `{"deleted": "023G"}`, or `404`.

### 6.12 `GET /v1/me/results`

The student's latest search, saved by `POST /v1/recommendations` (one per student; a new search replaces
it). Use it at app start to fill the form and show the results again, on any device.

```json
{"form": {"stream": "Physical Science", "al": [...], "cgt": 40, "z_score": 1.56, "admission_district": "Kandy",
          "ds_division": "Gangawata Korale", "ol": [...], "preferences": "engineering, design",
          "use_llm": false, "suggestions": 20},
 "report": {"profile": {...}, "origin": {...}, "bands": {...}, "rankings": {...}, "...": "..."},
 "used_llm": false, "saved_at": "2026-11-14T06:20:00+00:00"}
```

`form` is exactly the body of 6.4; `report` is exactly its `report`. `404` before the first search.

---

## 7. Errors

Every error has the same body, so you only need one error handler:

```json
{"errors": ["Choose three different A/L subjects"]}
```

| Status | Meaning | What the app should do |
|---|---|---|
| `400` | Valid request that can't be served (bad combination, unknown course, feature not configured) | Show `errors` to the user |
| `401` | Not signed in, or the sign-in expired | Refresh the Supabase session and retry once; otherwise show the sign-in screen |
| `404` | Wrong path, or no saved chat for that course (6.10, 6.11) | For chats: show an empty chat. Otherwise a bug: check the URL |
| `409` | Career research already running for another course | Show the message, and retry later |
| `429` | Daily limit reached (chat, AI search or research) | Show `errors`; the limit resets at midnight Sri Lanka time |
| `422` | Body doesn't match the schema. Messages look like `"cgt: Field required"` or `"al.0.grade: ..."` | Bug in the client, or missing form validation |
| `500` | Server error | Show "Something went wrong", and retry |
| `502` | OpenAI failed or timed out | Show "Couldn't answer right now, try again" |
| network error / timeout | Server unreachable or too slow | Check the base URL (3.1) and timeout (3.4) |

---

## 8. Code examples

### 8.1 TypeScript (web, React Native)

```ts
const BASE_URL = "http://127.0.0.1:8780";   // from config
// Supabase client for sign-in (project URL + publishable key from the backend owner):
//   import { createClient } from "@supabase/supabase-js";
//   const supabase = createClient(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY);
//   await supabase.auth.signInWithPassword({ email, password });

export class ApiError extends Error {
  constructor(public status: number, public errors: string[]) { super(errors.join(" ")); }
}

async function api<T>(path: string, init: RequestInit = {}, timeoutMs = 90_000): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  const token = (await supabase.auth.getSession()).data.session?.access_token;   // supabase-js client
  try {
    const res = await fetch(BASE_URL + path, {
      ...init,
      signal: ctrl.signal,
      headers: { "Content-Type": "application/json", ...(token && { Authorization: `Bearer ${token}` }), ...init.headers },
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new ApiError(res.status, body.errors ?? [`Request failed (${res.status})`]);
    return body as T;
  } finally {
    clearTimeout(timer);
  }
}

// 1. form values
const options = await api<any>("/v1/options");

// 2. recommendations
const { report } = await api<any>("/v1/recommendations", {
  method: "POST",
  body: JSON.stringify({
    stream: "Physical Science",
    al: [{ subject: "Combined Mathematics", grade: "A" }, { subject: "Physics", grade: "B" },
         { subject: "Chemistry", grade: "C" }],
    ol: [{ subject: "Science", grade: "B" }, { subject: "English", grade: "B" }, { subject: "Mathematics", grade: "A" }],
    cgt: 40, z_score: 1.56, admission_district: "Kandy", ds_division: "Gangawata Korale",
    preferences: "engineering, design", use_llm: false,
  }),
});

// 3. chat about one course
const course = report.bands.strong[0];
const student = {
  stream: report.profile.stream, al_results: report.profile.al_results, z_score: report.profile.z_score,
  admission_district: report.profile.admission_district,
  home: `${report.origin.ds_division} (${report.origin.district})`, interests: report.preferences?.text ?? "",
};
const history: { role: "user" | "assistant"; content: string }[] = [];   // one per course, kept by the app

async function ask(question: string) {
  const reply = await api<any>("/v1/chat", { method: "POST", body: JSON.stringify({ question, course, student, history }) });
  history.push({ role: "user", content: question }, { role: "assistant", content: reply.answer });
  if (reply.career?.job?.state === "running") pollCareer(course.course_name, (s) => console.log(s.job?.message));
  return reply;
}

// 4. poll career research
async function pollCareer(courseName: string, onUpdate: (s: any) => void) {
  for (;;) {
    const s = await api<any>(`/v1/career-outlook?course=${encodeURIComponent(courseName)}`);
    onUpdate(s);
    if (s.job?.state !== "running") return s;
    await new Promise((r) => setTimeout(r, 5000));
  }
}
```

### 8.2 Dart / Flutter (package `http`)

```dart
import 'dart:convert';
import 'package:http/http.dart' as http;

class ApiError implements Exception {
  final int status; final List<String> errors;
  ApiError(this.status, this.errors);
  @override String toString() => errors.join(' ');
}

class CampusYamuApi {
  CampusYamuApi(this.baseUrl);
  final String baseUrl;            // e.g. http://10.0.2.2:8780 on the Android emulator

  // supabase_flutter keeps the session fresh; the token is the signed-in student's
  Map<String, String> get _headers {
    final token = Supabase.instance.client.auth.currentSession?.accessToken;
    return {
      'Content-Type': 'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
    };
  }

  Future<Map<String, dynamic>> _send(Future<http.Response> req) async {
    final res = await req.timeout(const Duration(seconds: 90));
    final body = res.body.isEmpty ? <String, dynamic>{} : jsonDecode(utf8.decode(res.bodyBytes));
    if (res.statusCode >= 400) {
      throw ApiError(res.statusCode, List<String>.from(body['errors'] ?? ['Request failed (${res.statusCode})']));
    }
    return body as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> options() =>
      _send(http.get(Uri.parse('$baseUrl/v1/options'), headers: _headers));

  Future<Map<String, dynamic>> recommendations(Map<String, dynamic> form) =>
      _send(http.post(Uri.parse('$baseUrl/v1/recommendations'), headers: _headers, body: jsonEncode(form)));

  Future<Map<String, dynamic>> chat({required String question, required Map<String, dynamic> course,
          Map<String, dynamic> student = const {}, List<Map<String, String>> history = const []}) =>
      _send(http.post(Uri.parse('$baseUrl/v1/chat'), headers: _headers,
          body: jsonEncode({'question': question, 'course': course, 'student': student, 'history': history})));

  Future<Map<String, dynamic>> careerOutlook(String course) => _send(http.get(
      Uri.parse('$baseUrl/v1/career-outlook').replace(queryParameters: {'course': course}), headers: _headers));

  Future<Map<String, dynamic>> startCareerResearch(String course) =>
      _send(http.post(Uri.parse('$baseUrl/v1/career-outlook/research'), headers: _headers,
          body: jsonEncode({'course': course})));

  /// Polls every 5 s until the research job is no longer running.
  Stream<Map<String, dynamic>> watchCareer(String course) async* {
    while (true) {
      final s = await careerOutlook(course);
      yield s;
      if (s['job']?['state'] != 'running') return;
      await Future.delayed(const Duration(seconds: 5));
    }
  }
}
```

Always decode the body as UTF-8, as above (`utf8.decode(res.bodyBytes)`). Handbook text and
citations contain characters such as `§`, `±` and `–`.

### 8.3 curl

```bash
BASE=http://127.0.0.1:8780
curl $BASE/v1/health
curl $BASE/v1/options
curl -X POST $BASE/v1/recommendations -H 'Content-Type: application/json' -d '{
  "stream":"Physical Science",
  "al":[{"subject":"Combined Mathematics","grade":"A"},{"subject":"Physics","grade":"B"},{"subject":"Chemistry","grade":"C"}],
  "cgt":40,"z_score":1.56,"admission_district":"Kandy","ds_division":"Gangawata Korale"}'
curl "$BASE/v1/career-outlook?course=Law"
# with sign-in on: add  -H "Authorization: Bearer $TOKEN"  (a signed-in student's Supabase access token)
```

---

## 9. Performance and limits

- **One heavy request at a time.** The server runs `/recommendations`, `/chat` and
  `/career-outlook` one after another on a single worker. Two users chatting at once means the
  second waits for the first. `/v1/health` always answers immediately. This is fine for
  development and small pilots. Tell the backend owner before a public launch.
- **Typical times:** recommendations 1–5 s (20–40 s with `use_llm`). Chat 5–20 s. Career
  research 3–10 minutes in the background, one course at a time across the whole server.
- **Cache on the client:** `/v1/options` per app session, and the `report` for as long as the
  form inputs don't change. Re-run recommendations only when the student edits the form.
- **Chat history:** signed in, the server keeps it; don't send `history`. Without sign-in it uses the last
  8 turns (at most 40 accepted).
- **Daily limits:** see [6](#6-endpoint-reference). `429` when reached.
- **Cost:** `use_llm`, `/v1/chat` and career research use paid APIs. Don't call them
  automatically, in loops, or on every keystroke. Trigger them from explicit user actions.

---

## 10. Going to production

Checklist for the backend owner (share it with whoever deploys):

1. **HTTPS.** Run the API behind a reverse proxy that terminates TLS. For example, with Caddy:
   ```
   api.example.com {
       reverse_proxy 127.0.0.1:8780
   }
   ```
   Set the proxy's upstream read timeout to 120 s or more (chat and AI recommendations are slow).
2. **Sign-in.** Set `SUPABASE_URL` (and `SUPABASE_DB_URL` for chat memory). Every endpoint except
   `/v1/health` then needs a signed-in student's token. Without `SUPABASE_URL` the API is open: never
   deploy it that way.
3. **CORS.** Set `API_CORS_ORIGINS=https://www.example.com` (comma-separated for several) so only
   your web app's origin can call the API from a browser. Native apps aren't affected.
4. **Bind address.** In Docker, the API listens on `0.0.0.0:8780` inside the container. Expose it
   only to the proxy, not directly to the internet.
5. **Persistent cache.** Keep `data/cache/` on a volume (docker-compose already does) so career
   research survives restarts.
6. **Monitoring.** Point uptime checks at `GET /v1/health`.

---

## 11. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Every band is empty | `cgt` is below the pass mark, or the A/L subjects don't qualify for anything. Try the example in 6.4 |
| Everything is in `no_history` | No `z_score` was sent |
| `422 "cgt: Field required"` | `cgt` is required. Send the Common General Test mark |
| `400 "Choose three different A/L subjects"` | Two `al` entries have the same subject |
| `400 "The course chat needs OPENAI_API_KEY in .env"` | Server has no OpenAI key. Check `llm_available` and hide chat when it's false |
| `401 Sign in first` / `Sign-in expired` | Send `Authorization: Bearer <session.access_token>`; refresh the Supabase session when it expires |
| Android Emulator can't connect to `127.0.0.1` | Use `http://10.0.2.2:8780` |
| Phone can't connect | Start with `--host 0.0.0.0`, use the computer's LAN IP, same Wi-Fi, allow port 8780 in the firewall, and allow cleartext HTTP in debug (3.2) |
| `CLEARTEXT communication not permitted` (Android) / ATS error (iOS) | See 3.2 |
| Browser: `blocked by CORS policy` | Add your web app's origin to `API_CORS_ORIGINS` and restart the API |
| Chat or recommendations time out | Raise the client timeout to 90 s+. Another request may be running first (section 9) |
| Garbled characters (`Â§`, `Ã`) | Decode the response as UTF-8 |
| `/v1/career-outlook` shows `available: false` | Server lacks research keys. `missing_keys` lists them |
| `409` on research | Another course is being researched. Wait for it, then retry |
| `Address already in use` when starting | Port 8780 is taken: `make api API_PORT=8781` (and update your base URL) |

---

## 12. Versioning

- Paths start with `/v1`. Within `/v1`, changes are **additive only**: new endpoints, new optional
  request fields, new response fields. Write clients that ignore unknown fields.
- Removing or renaming a field, or changing its meaning, goes to `/v2`, and `/v1` keeps working
  during a transition period.
- `GET /v1/health` → `version` gives the backend version, and `/openapi.json` always matches the
  running server.
