# CampusYamu UI mockup

A clickable mockup of the student app on top of the `/v1` API. Friendly app style matching
the illustrations: navy `#14185C`, royal blue `#4F6FE8`, lavender `#C9B8F5`, mustard `#F2B84B`
(highlights only) on `#FAF9FF`, with `#ECE4FD` figure panels. Plus Jakarta Sans, rounded white
cards, pill chips, a navy bottom bar on phones. Flat colours only. Plain Node.js, no dependencies.

```bash
cd ui-mockup
npm start                 # http://localhost:5173, mock /v1 data (from a real saved report)
npm run live              # forwards /v1 to the real API on :8780 (run `make api` with sign-in off)
```

Screens: language (සිංහල / தமிழ் / English, first visit only) → landing page (what CampusYamu is,
with Sign in as a button) → sign-in (split card with figure) → results form (4 steps, live Z-score dial) →
analysing (live checklist of the five backend steps) → courses by admission band →
ranked order (timeline, three lists, reorders with motion) → course detail (cut-off chart,
handbook block, chat with citations and career-research progress) → account (daily limits, saved chats).

- `server.js`: static files, `/figures.json` (which figures exist), and a mock `/v1`
  (options, recommendations, chat, career-outlook, me).
- `mock/report.json`: trimmed copy of `outputs/student_report.json`.
- `public/styles.css`: the design tokens (`:root`) and components.
- Dark mode: a deep navy page (`#0B0E2B`) with lifted navy cards and light lavender-white text, in
  the same flat palette. Main buttons turn lavender with navy text. Navy as a fill (`--navy`, e.g.
  the advice card, banners, the phone tab bar) is a separate token from navy as text (`--ink`), so
  both work in either mode. It follows the device until the student picks Light or Dark with the
  sun/moon button in the top bar or under Appearance on the account page (saved as `cy.theme`;
  `index.html` applies it before the first paint). Illustrations switch to their royal-blue
  `<name>.dark.webp` copies (see `public/figures/README.md`). On phones the top bars show the logo mark only, so all the buttons fit.
- `public/app.js`: the screens; every call uses the real `/v1` request and response shapes.
- Landing page (`views.home` in `app.js`, `#/home`): hero, a "how it works" panel that stays
  pinned while you scroll and brings the four steps up one at a time (figure and progress bar change with them), big-number tiles, widening course-area cards, a chat preview,
  FAQ and a closing banner. Layout ideas from choreolabs.com, in the app's own style. The numbers
  are real counts from `data/processed/knowledge_graph/graph_data.json` (`LANDING_STATS`).
  Signed-out visitors land here; signed-in students go straight to their courses.
- `public/i18n.js`: all interface text in Sinhala, Tamil and English (`t(key)`). The choice is
  remembered in `localStorage` (`cy.lang`) and can be changed from the globe button in the top bar,
  on sign-in, or on the account page. Course and university names, handbook text, advice and chat
  answers stay as the API sends them (English). Sinhala/Tamil letters use Noto Sans Sinhala/Tamil.
  The Sinhala and Tamil wording is a first draft for a native speaker to check.
- `public/figures/`: drop illustrations here; names and slots are in its README.
- `public/brand/`: the logo. A "Y" that is a fork in the road (Yamu, "let's go"; choosing a
  course) with a mustard AI sparkle on the branch to take. `logo-mark.svg` (icon, also the
  favicon), `logo.svg` (icon + wordmark), `logo-mono.svg` (white, for dark backgrounds),
  `app-icon.svg` / `app-icon-512.png` / `apple-touch-icon.png` (full-bleed square icons).
  The wordmark in the SVGs is live text in Plus Jakarta Sans ExtraBold; convert it to outlines
  in a design tool before using the files outside the app.

Sign-in is faked here. The real app signs in with Supabase and sends `Authorization: Bearer <token>`.
