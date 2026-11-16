# campusyamu2.0 — Frontend Reference & Design Rules

This document is the authoritative reference for building the **campusyamu2.0** web frontend. Every UI component, style token, layout decision, and API integration must follow these rules.

For backend endpoints, schemas, and data contracts, see [API.md](API.md) and [ARCHITECTURE.md](ARCHITECTURE.md).

---

## 1. Brand & Design Philosophy

- **Website Name:** `campusyamu2.0`
- **Design Reference:** [`https://jaliyanimantha.com/`](https://jaliyanimantha.com/)
- **Core Aesthetic:** Clean, simple, modern, engineering-grade clarity. Generous white space, crisp `1px` borders, clear typographic hierarchy, and zero visual clutter.
- **Strict Visual Rules:**
  1. **White background** (`#FFFFFF`) as the primary canvas.
  2. **One major accent color: Blue** (`#1D4ED8`).
  3. **NO gradients anywhere** — do not use CSS `linear-gradient`, `radial-gradient`, `conic-gradient`, or gradient text/borders/buttons. All fills must be flat, solid colors.
  4. **Sans-serif typography only** — no serif display fonts or decorative scripts.

---

## 2. Design System & Tokens

### 2.1 Color Palette (White + Blue)

| Token | Hex | Usage |
|---|---|---|
| `--bg-canvas` | `#FFFFFF` | Main page background, primary cards, drawers |
| `--bg-subtle` | `#F8FAFC` | Secondary panels, table headers, input backgrounds, stat chips |
| `--bg-hover` | `#F1F5F9` | Hover state for neutral rows and ghost buttons |
| `--border-default` | `#E2E8F0` | Card borders, dividers, table rules, input borders |
| `--border-strong` | `#CBD5E1` | Hover borders, active input outlines |
| `--text-primary` | `#0F172A` | Headings, course titles, primary values |
| `--text-secondary` | `#475569` | Body copy, descriptions, table labels |
| `--text-muted` | `#64748B` | Captions, footnotes, citations, placeholders |
| `--blue-primary` | `#1D4ED8` | Primary CTA buttons, active tabs, selected items, focus rings |
| `--blue-hover` | `#1E40AF` | Hover state on primary blue buttons/links |
| `--blue-tint` | `#EFF6FF` | Subtle blue surface for active row highlights, info banners, selected chips |
| `--blue-border` | `#BFDBFE` | Borders around `--blue-tint` containers |

#### Restrained Semantic & Band Indicators
To preserve the white-and-blue identity without turning the page into a rainbow, Z-score bands (`strong`, `competitive`, `reach`, `unlikely`, `no_history`) and error states must use **clean white/neutral pills with a solid indicator dot or subtle border**, rather than loud saturated fills:

| State / Band | Indicator Treatment |
|---|---|
| `strong` | Solid `#1D4ED8` dot + `#0F172A` text on `#EFF6FF` pill (`1px solid #BFDBFE`) |
| `competitive` | Solid `#3B82F6` dot + `#0F172A` text on `#F8FAFC` pill (`1px solid #E2E8F0`) |
| `reach` | Solid `#64748B` dot + `#0F172A` text on `#F8FAFC` pill (`1px solid #CBD5E1`) |
| `unlikely` | Outlined `#94A3B8` dot + `#475569` text on `#FFFFFF` pill (`1px solid #E2E8F0`) |
| `no_history` | Dash icon + `#64748B` text on `#F8FAFC` pill (`1px solid #E2E8F0`) |
| Error / Validation | `#B91C1C` text on `#FEF2F2` background (`1px solid #FECACA`) |

### 2.2 Typography (Sans-Serif)

- **Font Stack:**
  ```css
  --font-sans: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  ```
  *(Load `Inter` cleanly via `@fontsource/inter` or Google Fonts; fall back to system sans-serif.)*
- **Type Scale:**
  - Page / Brand Title: `20px`–`24px`, `font-weight: 700`, `letter-spacing: -0.02em`
  - Section Heading (`h2`): `18px`, `font-weight: 600`, `letter-spacing: -0.015em`
  - Card / Course Title (`h3`): `15px`–`16px`, `font-weight: 600`
  - Body Text: `14px`–`15px`, `line-height: 1.55`
  - Labels / Table Headers / Badges: `12px`–`13px`, `font-weight: 500`
- **Numeric Alignment:** Always apply `font-variant-numeric: tabular-nums` to Z-scores, cut-offs, margins, intake counts, and travel times (`car_min`, `bus_min_est`, `road_km`).

### 2.3 Shape, Spacing & Elevation

- **Border Radius:** `8px` for cards/panels, `6px` for buttons/inputs, `9999px` for status pills.
- **Borders over Shadows:** Use crisp `1px solid #E2E8F0` borders for structure. Avoid heavy drop shadows; use at most a subtle shadow (`0 4px 16px rgba(15, 23, 42, 0.06)`) only on floating slide-over drawers.
- **Whitespace:** Generous padding (`16px`–`24px` inside panels, `24px`–`32px` between major sections) inspired by the clean editorial spacing of `https://jaliyanimantha.com/`.

---

## 3. Recommended Tech Stack & Directory Layout

Place the modern frontend in `frontend/` at the repository root:

```text
frontend/
├── package.json
├── vite.config.ts
├── tsconfig.json
├── index.html
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── styles/
    │   └── tokens.css          # White + Blue CSS variables, tabular-nums utilities
    ├── api/
    │   ├── client.ts           # Fetch wrapper (90s timeout, X-API-Key, ApiError)
    │   ├── schema.d.ts         # Auto-generated from /openapi.json
    │   └── types.ts            # Typed report, course row, rankings, and chat models
    ├── state/
    │   └── sessionStore.ts     # Form inputs, latest report, per-course chat history
    ├── components/
    │   ├── Header.tsx          # campusyamu2.0 brand, /v1/health badge, Edit Results
    │   ├── ProfileForm.tsx     # Step 1: A/L, O/L, CGT, Z-score, District/DS, Interests
    │   ├── SummaryStrip.tsx    # Profile recap & eligibility counts
    │   ├── RankingsView.tsx    # Distance (main), Preference, Z-score + feedback + parts bar
    │   ├── BandsExplorer.tsx   # strong/competitive/reach/unlikely/no_history + filters
    │   ├── CourseDrawer.tsx    # Slide-over container for selected course
    │   ├── CourseOverview.tsx  # Z-score stats, O/L checks, travel, Markdown handbook
    │   ├── CourseChat.tsx      # Per-course Q&A with [S1]/[C] citations
    │   └── CareerOutlook.tsx   # Cached outlook + "Research careers" + 5s polling
    └── utils/
        └── format.ts           # UTF-8 safe formatting, band labels, travel formatting
```

### Key Libraries
- **React + TypeScript + Vite**: Fast local dev and static `dist/` output.
- **Tailwind CSS v4**: Utility-first styling mapped to the `--bg-*`, `--border-*`, `--text-*`, and `--blue-*` tokens.
- **TanStack Query**: Caches `GET /v1/options` per session, manages `POST /v1/recommendations` and `POST /v1/chat` mutations, and handles `GET /v1/career-outlook` 5-second polling.
- **`openapi-typescript`**: Generates `src/api/schema.d.ts` directly from `http://127.0.0.1:8780/openapi.json`.
- **`react-markdown`**: Renders `course_details[course_code].blocks[details_block].text` and chat responses.
- **`lucide-react`**: Clean monochrome/blue `1.5px` stroke icons.

---

## 4. API & Reliability Rules

All API contracts are defined in [docs/API.md](API.md) and [src/campusyamu/api/schemas.py](../src/campusyamu/api/schemas.py).

1. **Base URL & Auth:**
   - Read `VITE_API_BASE_URL` (default `http://127.0.0.1:8780`) and optional `VITE_API_KEY` (`X-API-Key` header).
2. **Timeouts:**
   - Set an `AbortController` timeout of **at least 90,000 ms (90s)** on `POST /v1/recommendations` and `POST /v1/chat`.
3. **Single-Worker Guard:**
   - The FastAPI backend executes `/v1/recommendations`, `/v1/chat`, and `/v1/career-outlook` sequentially on one worker thread. Disable submit buttons while a heavy request is in flight so duplicate requests cannot queue up.
4. **Unified Error Handling:**
   - Every error returns `{ "errors": string[] }`. Handle `400` (validation/business rule), `401` (API key), `409` (another career research job running), `422` (schema mismatch), `500`, `502`, and network timeouts in one `ApiError` handler.
5. **UTF-8 Safety:**
   - Preserve special characters in handbook text and citations (`§`, `±`, `–`).
6. **Session Persistence:**
   - Persist form inputs, the latest `report`, and per-course `chat` histories (keyed by `uni_code`) in `sessionStorage` so accidental refreshes do not lose a 20–40s AI report.

---

## 5. Screen-by-Screen Functional Specification

### 5.1 Header Bar (`Header.tsx`)
- Left: **`campusyamu2.0`** wordmark + subtle subtitle (`UGC Student Handbook 2024/2025`).
- Right:
  - Compact API status pill from `GET /v1/health` (`Online` / `AI Ready` or `Offline Mode`).
  - **"Edit Results"** button (visible when a `report` is loaded) to return to or toggle the intake form.

### 5.2 Student Profile & Results Form (`ProfileForm.tsx`)
- Hydrate options once from `GET /v1/options` on app load.
- **Stream & A/L Subjects:**
  - Changing `stream` pre-fills the 3 A/L subjects from `stream_hints[stream].defaults`.
  - Enforce 3 distinct A/L subjects client-side before submit.
  - Show a non-blocking soft notice if subjects differ from `stream_hints[stream].allowed` / `required_any` / `required_all` (never block submission).
- **CGT & Z-score:**
  - `cgt` (integer `0–100`) is **required**.
  - `z_score` is optional (show a note: *"Without a Z-score, eligible courses appear under No History"*).
- **O/L Grades:**
  - Collapsible optional section for `ol_subjects` (`Science`, `English`, `Mathematics`) using `ol_grades`. Omit empty entries from the request payload.
- **Location (2-Step Picker):**
  - `admission_district` from `districts`.
  - Home District (`districts`) → `ds_division` (`ds_divisions[homeDistrict]`).
- **Interests & AI Toggle:**
  - Free-text `preferences` (max 2000 chars).
  - `use_llm` checkbox: **only render when `options.llm_available === true`**. Label clearly that AI mode takes 20–40s.
- **Loading State:**
  - Show a clean inline progress indicator with elapsed seconds while waiting for `POST /v1/recommendations`.

### 5.3 Recommendations Workspace (`SummaryStrip.tsx`, `RankingsView.tsx`, `BandsExplorer.tsx`)
- **Summary Strip:** Shows student stream, Z-score, district, and `report.counts` (`can_apply`, `with_conditions`, `band_strong`, etc.).
- **Primary Tabs:**
  1. **Recommended Order** (Default — `report.rankings.distance`, with sub-pills for `preference` and `zscore`):
     - Display `title` and `feedback.summary` in a `#EFF6FF` (`--blue-tint`) callout card with `1px solid #BFDBFE`.
     - Collapsible **"Close Calls & What-If Advice"** section rendering `feedback.close_calls` and `feedback.priorities`.
     - Course rows showing `position`, `course_name`, `university`, `band` badge, `latest_cutoff`, `car_min` / `bus_min_est`, `flags` (e.g., `aptitude test`), and a **flat 3-segment horizontal bar** for `parts: { interest, cutoff, distance }` using solid shades of blue/slate (no gradients).
  2. **All Eligible by Band** (`report.bands`):
     - Render sections in exact order: `strong` → `competitive` → `reach` → `unlikely` → `no_history`.
     - Include client-side search (course name / university) and quick filter chips (`All`, `Ready to Apply`, `With Conditions`, `Same District`).
     - Use `uni_code` as the React list key. Treat all fields except `uni_code`, `course_code`, `course_name`, `university`, and `band` as optional.

### 5.4 Course Detail Drawer (`CourseDrawer.tsx`)
Clicking any course row opens a right-hand slide-over drawer (`max-width: 640px` on desktop, full-screen sheet on mobile) so the user keeps their place in the list:

1. **Overview & Handbook (`CourseOverview.tsx`):**
   - Header: `course_name`, `university`, `uni_code`, `band` pill, `group` status (`can_apply` vs `with_conditions`).
   - Z-score card: `latest_cutoff` (`latest_year`), `predicted_cutoff ± uncertainty`, `expected_margin`, `years_met / years_compared`, `proposed_intake`, and `reason` paragraph.
   - Travel & O/L card: `site`, `site_district`, `car_min`, `bus_min_est`, `road_km`, plus `ol_met`, `ol_failed`, `ol_unknown` chips.
   - **Handbook Section:** Render `report.course_details[row.course_code].blocks[row.details_block].text` using `react-markdown`, with a `citation` badge (e.g., `Handbook §2.2.4.5, p. 78`).

2. **Course Chat (`CourseChat.tsx`):**
   - **Only enabled when `llm_available === true`** (otherwise show a clean muted notice).
   - Send the **entire unchanged course row** (plus `order3_position`, `parts`, and `order3_note` if present in `rankings.distance`), the `student` object built from `report.profile` + `report.origin` + `report.preferences.text`, and up to the **last 8 turns** of `history` for this `uni_code`.
   - Provide 3 clickable starter chips (e.g., *"What are the career prospects?"*, *"Is there an aptitude test?"*, *"What are the O/L requirements?"*).
   - Render `answer` preserving line breaks, highlight `[S1]` / `[C]` tags, and list `sources` underneath (`citation`, `title`, and clickable external `links`).
   - If the response includes `career.job.state === "running"`, automatically start Career Outlook polling.

3. **Career Outlook (`CareerOutlook.tsx`):**
   - On drawer open, call `GET /v1/career-outlook?course=<encodeURIComponent(course_name)>`.
   - If `available === false`, hide the **"Research Career Prospects"** button.
   - If `outlook` exists, display `overall.label`, `overall.summary`, `overall.confidence`, and `sources` count.
   - If `outlook` is `null` and `available === true`, show an explicit **"Research Career Prospects"** button (`POST /v1/career-outlook/research`) with a note that research takes 3–10 minutes and runs one course at a time.
   - Poll `GET /v1/career-outlook` every **5 seconds** while `job.state === "running"`, displaying `job.message` until `done` or `failed`. Handle `409` gracefully by informing the user another course is currently being researched.

---

## 6. Build, Deployment & Integration

- **Local Development:**
  - Terminal 1: `make api` (FastAPI on `http://127.0.0.1:8780`)
  - Terminal 2: `cd frontend && npm run dev` (Vite dev server with proxy or `VITE_API_BASE_URL=http://127.0.0.1:8780`)
- **Production Static Build:**
  - `npm run build` outputs to `frontend/dist/`.
  - Update [src/campusyamu/web/server.py](../src/campusyamu/web/server.py) (or Docker) to serve `frontend/dist/` on port `8770` so `make web` and `docker compose up --build -d` continue to work out of the box.

---

## 7. Implementation Phases

Build the frontend incrementally in five focused phases. Each phase should be verified against a running `make api` instance before moving to the next.

### Phase 1 — Project Setup, Design Tokens & Typed API Layer
- Initialize `frontend/` with Vite, React, TypeScript, Tailwind CSS v4, TanStack Query, `lucide-react`, and `react-markdown`.
- Configure `src/styles/tokens.css` with the White + Blue palette (`#FFFFFF`, `#F8FAFC`, `#1D4ED8`), sans-serif font stack (`Inter`), `tabular-nums` utilities, and **zero gradients**.
- Generate OpenAPI types from `http://127.0.0.1:8780/openapi.json` into `src/api/schema.d.ts` and add typed `report` models in `src/api/types.ts`.
- Build `src/api/client.ts` with `90s+` `AbortController` timeout, optional `X-API-Key` header, and unified `ApiError` (`{ errors: string[] }`).
- **Done when:** `Header.tsx` renders the `campusyamu2.0` wordmark and live `GET /v1/health` status badge.

### Phase 2 — Student Profile & Results Intake (`ProfileForm.tsx`)
- Hydrate streams, A/L subjects, O/L subjects, districts, and DS divisions from `GET /v1/options` (cached per session).
- Implement `stream_hints` auto-fill for A/L defaults and non-blocking soft warnings.
- Enforce 3 distinct A/L subjects, required `cgt` (`0–100`), optional `z_score`, collapsible O/L grades, and the 2-step Home District → DS Division picker.
- Gate the `use_llm` toggle on `options.llm_available === true`.
- Wire `POST /v1/recommendations` with a single-worker duplicate-submit guard and elapsed-time loading indicator.
- **Done when:** Submitting valid results returns and persists `report` in `sessionStorage`, and `400`/`422` errors display cleanly inline.

### Phase 3 — Recommendations Workspace (`SummaryStrip.tsx`, `RankingsView.tsx`, `BandsExplorer.tsx`)
- Build `SummaryStrip.tsx` displaying student profile chips and `report.counts`.
- Build `RankingsView.tsx` defaulting to `rankings.distance` (with sub-tabs for `preference` and `zscore`), `feedback.summary`, collapsible `close_calls` / `priorities`, and the flat 3-segment `parts` bar (`interest`, `cutoff`, `distance`).
- Build `BandsExplorer.tsx` rendering `strong`, `competitive`, `reach`, `unlikely`, and `no_history` in order, with client-side search and quick filter chips (`All`, `Ready to Apply`, `With Conditions`, `Same District`).
- **Done when:** Users can switch between Ranked Order and Band views, filter courses, and click any row to select it.

### Phase 4 — Course Drawer, Handbook, Chat & Career Polling (`CourseDrawer.tsx`)
- Build the slide-over `CourseDrawer.tsx` (desktop side drawer, mobile full-screen sheet).
- Build `CourseOverview.tsx` with Z-score metrics, travel times, O/L check chips, and Markdown-rendered handbook sections (`course_details[course_code].blocks[details_block].text`).
- Build `CourseChat.tsx` (enabled when `llm_available === true`) with per-`uni_code` `sessionStorage` history (sending up to 8 turns + full course row + `order3_*` context), starter chips, and clickable `[S1]`/`[C]` source citations.
- Build `CareerOutlook.tsx` with `GET /v1/career-outlook`, explicit `POST /v1/career-outlook/research` trigger (hidden if `available === false`), `409` conflict handling, and 5-second polling while `job.state === "running"`.
- **Done when:** Clicking a course opens its handbook details, chat answers with citations, and career research polls cleanly to `done` or `failed`.

### Phase 5 — Polish, Accessibility & Static Packaging
- Audit WCAG AA contrast, keyboard navigation (`Escape` to close drawer, `aria-selected` on tabs), and responsive mobile layouts (`< 768px`).
- Verify `npm run build` produces `frontend/dist/` cleanly.
- Wire `frontend/dist/` into [src/campusyamu/web/server.py](../src/campusyamu/web/server.py), [Makefile](../Makefile), and [docker-compose.yml](../docker-compose.yml) so `make web` and `docker compose up --build -d` serve the new frontend on port `8770`.
- **Done when:** All items in Section 8 pass against a live backend.

---

## 8. Verification Checklist Before Shipping Frontend Changes

- [ ] Background is `#FFFFFF` with `#F8FAFC` secondary surfaces; **zero CSS gradients** anywhere in stylesheets or components.
- [ ] Only **one major accent color** (`#1D4ED8` Blue) is used for primary actions and active states.
- [ ] All text uses the **sans-serif** font stack; numeric columns use `tabular-nums`.
- [ ] `GET /v1/options` populates all dropdowns (no hard-coded subjects or districts).
- [ ] `POST /v1/recommendations` and `POST /v1/chat` use a `90s+` timeout and disable duplicate submissions while pending.
- [ ] `use_llm` and Course Chat are hidden/disabled when `llm_available === false`; Career Research button is hidden when `available === false`.
- [ ] Career polling stops immediately when `job.state` becomes `done` or `failed`.
- [ ] Mobile viewport (`< 768px`) stacks cleanly and the course drawer behaves as a full-screen sheet.
