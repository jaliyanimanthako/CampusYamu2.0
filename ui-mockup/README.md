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

Screens: sign-in (split card with figure) → results form (4 steps, live Z-score dial) →
analysing (live checklist of the five backend steps) → courses by admission band →
ranked order (timeline, three lists, reorders with motion) → course detail (cut-off chart,
handbook block, chat with citations and career-research progress) → account (daily limits, saved chats).

- `server.js`: static files, `/figures.json` (which figures exist), and a mock `/v1`
  (options, recommendations, chat, career-outlook, me).
- `mock/report.json`: trimmed copy of `outputs/student_report.json`.
- `public/styles.css`: the design tokens (`:root`) and components.
- `public/app.js`: the screens; every call uses the real `/v1` request and response shapes.
- `public/figures/`: drop illustrations here; names and slots are in its README.

Sign-in is faked here. The real app signs in with Supabase and sends `Authorization: Bearer <token>`.
