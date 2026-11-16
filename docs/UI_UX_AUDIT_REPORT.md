# UI/UX Audit & Growth Strategy Report: Attracting Sri Lankan Students (Ages 16–25)

**Target Audience:** Sri Lankan students aged 16–25 (O/L graduates choosing A/L streams, A/L candidates, university applicants awaiting UGC selection, and early undergraduates)  
**Scope Inspected:** `frontend/src/` (React 19, TypeScript, Tailwind CSS v4, Vite)

---

## Executive Summary

`CampusYamu2.0` already has a **high-trust, technically solid foundation**: trilingual support (`EN | සිං | தமிழ்`), dark/light mode, transparent Z-score banding, travel-time estimates from the student's DS division, handbook-cited AI chat, and career outlook research.

However, from a **Senior UI/UX Engineer** perspective, the current frontend feels like an **institutional / government utility portal** rather than a **modern student companion**. For Sri Lankan Gen-Z users (16–25) who discover tools via TikTok, Instagram, and WhatsApp groups—and primarily browse on mobile devices—three major gaps limit adoption and retention:

1. **High First-Visit Friction:** Users must complete a 4-section intake form (including CGT marks and DS divisions) before seeing *any* university or degree value.
2. **Developer-Centric Framing & Aesthetic:** Technical labels (`campusyamu2.0`, `Checking API`, `make api`, `AI Ready`) and a strictly flat, clinical layout reduce emotional appeal and trust.
3. **Missing Mobile & Social Loops:** No UGC preference-order shortlist/export, no WhatsApp/IG-ready shareable cards, and `sessionStorage` wipes student data when a mobile browser tab closes.

---

## 1. Current Frontend Strengths (Keep & Amplify)

| Area | What Works Well | Code Reference |
| :--- | :--- | :--- |
| **Trilingual Equity** | Native `EN \| සිං \| தமிழ்` switcher with `Noto Sans Sinhala` and `Noto Sans Tamil` web fonts. Crucial for island-wide adoption. | [Header.tsx](../frontend/src/components/Header.tsx), [index.html](../frontend/index.html) |
| **Explainable Rankings** | `PartsBar` breaks down Interest, Cut-off, and Distance contributions, and `RankingsView` offers 3 distinct sorting lenses (Distance, Preference, Z-score). | [RankingsView.tsx](../frontend/src/components/RankingsView.tsx) |
| **Realistic Local Context** | Factors in **Admission District** vs. **Home DS Division** with car and estimated bus travel times—solving a real Sri Lankan logistics pain point. | [CourseOverview.tsx](../frontend/src/components/CourseOverview.tsx) |
| **Grounded AI & Career Tab** | `CourseChat` cites handbook rules with inline badges (`[A1]`) and starter question chips; `CareerOutlook` surfaces future career context. | [CourseChat.tsx](../frontend/src/components/CourseChat.tsx), [CareerOutlook.tsx](../frontend/src/components/CareerOutlook.tsx) |
| **Theme & Accessibility** | Clean semantic HTML, `aria-label`/`role="tablist"` usage, and built-in Dark Mode (`html.dark`). | [tokens.css](../frontend/src/styles/tokens.css), [CourseDrawer.tsx](../frontend/src/components/CourseDrawer.tsx) |

---

## 2. Critical UX Friction Points Observed

### A. Brand Identity & Copy Feels Technical, Not Student-Friendly
- **Observation:** The header displays `campusyamu2.0` in lowercase with a technical status pill (`Checking API`, `AI Ready`, `Offline Mode`). When the backend is unreachable, `ProfileForm` instructs students: *"Start the backend with make api, or switch to local Demo Data..."*.
- **Impact:** 16–25 year olds are not software engineers. Seeing `API`, `2.0`, or `make api` breaks immersion and makes the product look like an unfinished developer tool.
- **Recommendation:**
  - Rebrand the visible title to **CampusYamu** (keep `2.0` out of the header) with a warm, aspirational tagline (e.g., *"Your Sri Lankan State University & Career Compass"*).
  - Replace the API status pill in production with a subtle indicator or move diagnostics to a footer/dev-only modal. If the backend is down, show a friendly message (*"We're refreshing our servers—explore sample results meanwhile!"*).

### B. High-Friction Onboarding & Exclusion of Ages 16–18
- **Observation:** `App.tsx` renders `HeroHome` stacked directly above the full 4-section `ProfileForm`. Users cannot explore courses, universities, or cut-off trends without submitting A/L subjects, grades, and a mandatory CGT mark (`0–100`).
- **Impact:**
  - **Ages 16–18 (O/L & Year 12 A/L students)** don't have A/L grades or CGT marks yet, so they bounce immediately.
  - **Mobile users** face a long vertical scroll of native `<select>` dropdowns before getting any reward.
- **Recommendation:**
  - **Add "Try Sample Student" One-Click Presets** in `HeroHome` (e.g., *"Physical Science · 1.56 Z-score · Gampaha"*, *"Bio Science · 1.42 · Kandy"*, *"Commerce · 1.65 · Colombo"*). One tap should immediately open a live `RankingsView` so curious students can see the magic in 2 seconds.
  - **Split Onboarding into a 3-Step Progressive Wizard** (or interactive cards) on mobile: *Step 1: Stream & Subjects* → *Step 2: Marks & District* → *Step 3: Vibe & Interests (tap-to-select chips like `Software`, `Medicine`, `Design`, `Finance`, `Near Home`)*.
  - **Add a "What-If / Pre-Results Explorer" Mode** with a Z-score slider (`0.50` to `2.50`) so 16–18 year olds can see: *"What Z-score do I need for Moratuwa Engineering or Colombo CS from my district?"*

### C. Mobile Ergonomics & Touch Interactions
- **Observation:**
  - `RankingsView.tsx` uses a `title="..."` attribute on `PartsBar` to show exact percentages (`Interest: 45%, Cutoff: 35%, Distance: 20%`). Hover tooltips **do not work on mobile touchscreens**.
  - `BandsExplorer.tsx` and `ProfileForm.tsx` rely on standard dropdowns and dense pill rows.
- **Impact:** Over 75%+ of Sri Lankan youth traffic is mobile. Hidden hover data and long `<select>` lists (like DS divisions) feel clunky on phones.
- **Recommendation:**
  - Replace `title` tooltips on `PartsBar` with an inline expandable legend or compact percentage labels (`45% Fit · 35% Z-Score · 20% Travel`).
  - Add **searchable comboboxes** for District / DS Division and **tap-friendly grade pills** (`A`, `B`, `C`, `S`, `F`) instead of `<select>` dropdowns for the 3 A/L subjects.

### D. Volatile Session State (`sessionStorage`)
- **Observation:** `sessionStore.ts` stores `campusyamu_form_state_v1`, `campusyamu_report_v1`, and chat history in `window.sessionStorage`.
- **Impact:** On iOS Safari and Android Chrome, switching to WhatsApp or another app often discards inactive tabs or clears `sessionStorage`, forcing students to re-enter all their A/L and O/L grades.
- **Recommendation:** Migrate persistence to `localStorage` with a visible **"Reset / New Student"** button in the header.

### E. Missing "Aha!" Visuals & Long AI Wait Experience
- **Observation:**
  - `CourseOverview.tsx` presents Z-score cut-offs as raw numbers (`Latest Cutoff`, `Predicted Cutoff`, `Expected Margin`).
  - Enabling AI interest matching (`useLlm`) takes **20–40 seconds** with only a static spinner and elapsed timer (`Analyzing eligible courses (14s)…`).
- **Recommendation:**
  - **Visual Z-Score Gauge:** Add a simple horizontal range bar in `CourseOverview` showing the student's Z-score dot relative to the past cut-off range. Visual feedback beats raw 4-decimal numbers (`± 0.0412`).
  - **Step-by-Step Progress Theater during AI Wait:** Show animated milestones during the 20–40s wait (*"1/4 Checking UGC eligibility rules… 2/4 Comparing 25-district cut-offs… 3/4 Calculating bus travel times… 4/4 Matching your career interests…"*), or stream/render deterministic eligibility results first and hydrate AI interest scores asynchronously.

---

## 3. High-Impact Features to Attract & Retain Sri Lankan Youth (16–25)

### 1. "My UGC Preference List" Builder & WhatsApp/PDF Export
- **Why it wins:** Every Sri Lankan A/L student must submit an ordered list of up to ~100+ course-university combinations to the UGC. Students currently struggle with spreadsheets and notebooks.
- **UX Design:** Add a **"★ Add to My List"** button on every course card in `RankingsView` and `BandsExplorer`, opening a reorderable **"My Draft UGC Order"** drawer with **Export to PDF / Copy for WhatsApp** (so they can send it to parents, teachers, or tuition masters for review).

### 2. Shareable "Uni Match Card" (Instagram Story & WhatsApp Ready)
- **Why it wins:** Organic growth in Sri Lanka happens in WhatsApp class groups and Instagram Stories.
- **UX Design:** A **"Share My Match Summary"** button that generates a clean, privacy-safe (no personal Z-score shown unless toggled) graphic card: *"My Top 3 State Uni Matches: 1. Computer Science (UCSC) · 2. Data Science (Sabaragamuwa) · 3. Software Eng (Kelaniya) — Found on CampusYamu"*.

### 3. Career & Campus Life Reality Check (Ages 18–25)
- **Why it wins:** 16–25 year olds care deeply about **starting salaries, remote/abroad opportunities, hostel vs. boarding costs, and campus culture**—not just academic eligibility.
- **UX Design:** Enhance `CareerOutlook.tsx` with quick-scan chips at the top:
  - **Typical Career Paths** (3–4 tags)
  - **Aptitude Test Alert** (already tracked via `row.aptitude_test`—make this a prominent actionable banner with typical deadlines/prep tips!)
  - **Commute vs. Boarding Indicator** (e.g., *"~2h 15m by bus from Gampaha — Boarding likely needed"*).

### 4. Side-by-Side Course Comparison
- **Why it wins:** Students constantly debate choices like *"UOM IT vs. UCSC CS"* or *"Peradeniya Engineering vs. Ruhuna Engineering"*.
- **UX Design:** Allow selecting 2–3 courses to compare Z-score safety band, intake size, bus time from home, and career outlook side-by-side.

### 5. Color Palette & Visual Hierarchy Audit (The "All-White" Critique)
- **What Works Today:**
  - High readability for Sinhala (`Noto Sans Sinhala`), Tamil (`Noto Sans Tamil`), and dense Z-score figures on `#FFFFFF` with `#0F172A` text (`tokens.css`).
  - Trustworthy, non-spammy academic feel and lightweight rendering on budget Android devices.
- **Why the Current All-White Design Hurts Youth Engagement:**
  - **Zero surface contrast (`#FFFFFF` cards on `#FFFFFF` canvas):** In `App.tsx` and `HeroHome.tsx`, the page background and card surfaces share `#FFFFFF`, separated only by thin `#E2E8F0` borders. This makes the interface look flat, clinical, or like a government PDF form rather than a modern student discovery app.
  - **Monotone blue/grey badges (`BandBadge.tsx`):** `Strong`, `Competitive`, `Reach`, and `Unlikely` all use blue or grey dots, forcing students to read every badge rather than scanning their admission chances visually.
  - **Missing emotional hook:** University admission is a major life milestone for 18–21 year olds; a strictly flat, colorless UI lacks the warmth and polish of apps they use daily.
- **Recommended Visual Upgrades (Clean, Not Neon):**
  1. **Separate Page Canvas vs. Card Surfaces:** Shift the main canvas background to a soft cool off-white (`#F8FAFC`) while keeping cards `#FFFFFF` so sections pop naturally.
  2. **Semantic Band Colors in `BandBadge.tsx`:**
     - **Strong:** Emerald green (`#ECFDF5` bg / `#059669` text)
     - **Competitive:** Blue (`#EFF6FF` bg / `#1D4ED8` text)
     - **Reach:** Amber/Orange (`#FFFBEB` bg / `#D97706` text)
     - **Unlikely:** Neutral Slate (`#F1F5F9` bg / `#64748B` text)
  3. **Give `HeroHome.tsx` Character:** Introduce a subtle, modern gradient or soft tinted hero surface paired with a visual preview of the student's match summary.

---

## 4. Prioritized Action Roadmap

| Priority | Initiative | Target Segment | Effort | Expected Impact |
| :--- | :--- | :--- | :--- | :--- |
| **P0 (Quick Win)** | Remove developer jargon (`make api`, `Checking API`, `2.0`), switch `sessionStorage` → `localStorage`, add 1-click **"Try Sample Student"** presets in `HeroHome`. | All (16–25) | Low (1–2 days) | Immediate drop in bounce rate; instant product comprehension. |
| **P0 (Quick Win)** | Semantic colors in `BandBadge.tsx` + mobile tap-friendly `PartsBar` legend + A/L grade pill buttons instead of `<select>`. | Mobile users | Low (1–2 days) | Faster scanning and much smoother mobile form completion. |
| **P1 (Core Growth)** | **"My UGC Shortlist"** builder (pin, reorder, export PDF/WhatsApp text) + **Shareable Match Card**. | A/L Applicants (18–21) | Medium (3–5 days) | Drives viral WhatsApp/IG sharing and repeat visits during UGC application window. |
| **P1 (Core Growth)** | **3-Step Progressive Intake** + **Z-Score "What-If" Slider** (explore without results). | O/L & Year 12–13 (16–18) | Medium (3–4 days) | Captures younger students 1–2 years before A/L results release. |
| **P2 (Differentiator)** | **Visual Z-Score History Bar** in `CourseOverview` + **2-Course Side-by-Side Compare** + **Progressive AI Loading Milestones**. | Decision-stage students | Medium–High | Higher confidence in final UGC preference ordering; lower AI wait drop-off. |
