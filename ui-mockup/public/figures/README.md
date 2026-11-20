# Figures

Flat corporate-memphis illustrations of one student, in the app palette:
lavender `#C9B8F5`, royal blue `#4F6FE8`, navy `#14185C`, mustard `#F2B84B`, white.
Background is a plain flat `#ECE4FD` (no gradient, no frame), the same colour as the
figure panels, so images blend in. About 1500 px wide, `.webp`, `.png` or `.svg`.

| File | Shape | Where it shows |
|---|---|---|
| `signin` | portrait | Sign-in page, left panel |
| `analysing` | 1:1 | Analysing page, right panel |
| `empty-chats` | 3:2 | Chats page when there are no chats |
| `area-engineering` | 3:2 | Course page and course cards: engineering, technology, architecture, QS… |
| `area-medicine` | 3:2 | Medicine, dental, nursing, pharmacy, health… |
| `area-it` | 3:2 | Computer science, IT, data science… |
| `area-management` | 3:2 | Management, commerce, accounting, tourism, hospitality… |
| `area-arts` | 3:2 | Arts, law, languages, media… |
| `area-science` | 3:2 | Everything else (physical/biological science, agriculture…) |

Dark mode: each figure has a `<name>.dark.webp` copy, the same drawing on a flat royal-blue
`#6880EE` background. In dark mode the app shows that copy on a `#6880EE` panel (`--fig-bg-dk`
in `../styles.css`). Only the copy for the current mode is downloaded. A figure without a
`.dark` copy keeps its lilac version, slightly dimmed. A new dark copy must use exactly
`#6880EE` for its background, or change `--fig-bg-dk` to match.

A missing figure shows a placeholder (hidden on course cards). The server lists what
exists at `/figures.json`. The course-to-area mapping is `area()` in `../app.js`.

Prompt ending used for every figure (put the subject first):

> Corporate memphis style with fine grainy noise texture, exaggerated proportions, small head,
> long arms, minimal face. Same character: lavender skin, dark navy curly hair, white t-shirt,
> mustard yellow trousers, royal blue backpack. Flat shapes, no gradients, no vignette, no card
> or frame, plain solid #EEE7FD background filling the whole image. Palette only: #C9B8F5
> lavender, #4F6FE8 royal blue, #14185C navy, #F2B84B mustard, white. No text.
