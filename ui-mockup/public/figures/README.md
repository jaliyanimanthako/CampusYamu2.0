# Figures

Clean editorial vector illustrations of one Sri Lankan student (curly navy hair, brown skin,
often white-and-yellow headphones) in a different pose for each slot, in the app palette:
lavender `#C9B8F5`, royal blue `#4F6FE8`, navy `#14185C`, mustard `#F2B84B`, white.
Only the character and what they hold or lean on: no floating props or splashes.
Background is a plain flat lilac (about `#EADFFD`, no gradient, no frame), close to the
figure panels (`--fig-bg`), so images blend in. About 1500 px wide, `.webp`, `.png` or `.svg`.

| File | Shape | Where it shows | Current image |
|---|---|---|---|
| `signin-journey-long.png` | portrait 1:2, 887×1774 | Sign-in page | extended lavender path with two long bends separating results, university study and graduation; purple cloak with gold trim |
| `signin` | landscape | Earlier sign-in illustration, retained | original student reading a map |
| `how-results.png` | 3:2, 1536×1024 | "How it works" step 1 | high-resolution restoration of the original student reading a map; original flat illustration style and lavender background |
| `how-checks.png` | 3:2, 1536×1024 | "How it works" step 2 | high-resolution restoration of the original thinking student and light bulb |
| `how-ask.png` | 3:2, 1536×1024 | "How it works" step 4 | high-resolution restoration of the original reclining student with headphones |
| `chat-companion.png` | transparent, 1155×1362 | Landing AI assistant chat preview | student sitting on the card's top-right edge, wearing headphones and holding a handbook |
| `faq-astronaut-v2.png` | transparent, 1254×1254 | Left side of the landing FAQ | same human student reclining in a mustard astronaut suit with bent knees and a globe raised overhead, following the user's pose reference |
| `analysing-search-duo.png` | portrait, 1122×1402 | Analysing page | two student search helpers facing opposite directions with large magnifying glasses, a handbook and a backpack |
| `analysing` | 1:1 | Earlier analysing illustration, retained | original student thinking with a light bulb |
| `empty-chats` | 3:2 | Chats page when there are no chats | student lying back with headphones (576 px: placeholder) |
| `area-engineering` | 3:2 | Course page and course cards: engineering, technology, architecture, QS… | hard hat, leaning on a bridge |
| `area-medicine` | 3:2 | Medicine, dental, nursing, pharmacy, health… | doctor with clipboard |
| `area-it` | 3:2 | Computer science, IT, data science… | sitting with a laptop (576 px: placeholder) |
| `area-it-hd.png` / `area-it-hd.dark.png` | 3:2, 1536×1024 | Landing Computing & IT card and hero mosaic | faithful high-resolution restoration of the original laptop student |
| `area-law.png` / `area-law.dark.png` | 3:2, 1536×1024 | Landing Law card | lawyer in a navy gown and white neck bands holding a lavender law book |
| `area-architecture.png` / `area-architecture.dark.png` | 3:2, 1536×1024 | Landing Architecture & Built Environment card | same character holding plans and a pencil beside an architectural model |
| `area-agriculture.png` / `area-agriculture.dark.png` | 3:2, 1536×1024 | Landing Agriculture, Food & Environment card | same character holding a produce crate and a seedling |
| `area-management` | 3:2 | Management, commerce, accounting, tourism, hospitality… | thinking with a tablet and lanyard |
| `area-arts` | 3:2 | Arts, law, languages, media… | painting a mural |
| `area-science` | 3:2 | Everything else (physical/biological science, agriculture…) | at a microscope (full scene, 4:3) |
| `stats-graduate` | 1:1, 1037×1037 | Not used at the moment (was the landing "handbook in numbers" tile) | graduate jumping in a gown (cropped square from "Joyful Graduate Leaping in Celebration", 1536×1024) |

`signin-journey-long.png` was made with the built-in imagegen tool by extending
`signin-journey-study.png` into a 1:2 portrait. Two long S-curves create visible stretches of
path between results, university study and graduation. The middle stage includes a laptop,
notebook, books and library arch; the graduate's indigo-purple cloak and mustard-gold trim
follow `stats-graduate.webp`. It is contained without cropping at 92% of the existing panel's
height; the card keeps its compact layout. The prompt is in `signin-journey-long.prompt.txt`.
Earlier sign-in variants and their prompts remain available.

`chat-companion.png` was generated with the built-in imagegen tool using `how-ask.png`
as a style reference. Its alpha background works in both themes without a dark copy.
The compact chat card reserves space above and beside the student; the hand and seat align
with the top rim while the legs hang outside the messages. The decorative image is hidden
from assistive technology. The complete generation prompt is in `chat-companion.prompt.txt`.

`analysing-search-duo.png` was generated with the built-in imagegen tool using the user's
two-person search reference for its arrangement and `chat-companion.png` for our student
character and brand style. Two students search in opposite directions, holding oversized
magnifying glasses at different heights. The transparent illustration is shown whole on the
analysing panel in both themes. The complete prompt is in `analysing-search-duo.prompt.txt`.
The earlier single-student `analysing-search.png` and original light-bulb artwork are retained.

`faq-astronaut-v2.png` was generated with the built-in imagegen tool using the user's
astronaut image for the reclined floating pose and `chat-companion.png` for the human
student's identity and illustration style. The face and hair remain visible through the helmet.
The transparent cutout works in both themes and is displayed without mirroring. On phones
it sits above the cards, aligned left. The complete prompt is in `faq-astronaut-v2.prompt.txt`.
The earlier `faq-astronaut.png` and its prompt remain available but are no longer displayed.

`stats-graduate` is shown whole (`object-fit: contain`, anchored to the bottom) below the count
badge. Both copies have a transparent background (the lilac flood-filled away, edges un-mixed),
because a baked-in background never displays exactly like the panel's CSS colour and shows as a
faint box. The dark copy differs only in its ground shadow, which is a darker blue.
The landing number tiles use inline SVG clip art (`STAT_ART` in `../app.js`), not files.

The landing hero is a 2×3 grid of six students (`HERO_FIGS` in `../app.js`): engineering,
medicine, IT and management from above, plus two hero-only figures, `hero-sports` (basketball)
and `hero-drama` (acting with a script).

The landing category grid uses `AREA_FIGURES` overrides for the high-resolution IT student,
the user's supplied actor illustration (`hero-drama`) for Arts & Design, and the lawyer for Law.
Nine categories are arranged in three columns on desktop, two on tablet and one on phones,
with complete titles and descriptions visible. The original `area-arts` painting remains available for arts course cards.
These two replacement illustrations and their dark-mode versions were generated with the
built-in imagegen tool; full prompts are in `area-it-hd.prompt.txt` and `area-law.prompt.txt`.
The architecture and agriculture illustrations use the same character and art-style reference,
`area-management.webp`. They and their dark-mode versions were generated with the built-in
imagegen tool; full prompts are recorded in `area-architecture.prompt.txt` and
`area-agriculture.prompt.txt`.

Course cards crop figures to a short strip anchored near the top (`.course .fig img` in
`../styles.css`), so keep the student's head in the top third of the image.

Dark mode: a figure can have a `<name>.dark.webp` copy, the same drawing on a flat royal-blue
`#6880EE` background. In dark mode the app shows that copy on a `#6880EE` panel (`--fig-bg-dk`
in `../styles.css`). Only the copy for the current mode is downloaded. A figure without a
`.dark` copy keeps its lilac version, slightly dimmed. The current dark copies were made by
swapping the plain background for `#6880EE` (edge pixels shifted to match). `area-arts` and
`area-science` have none yet: their scenes (mural wall, lab desk) are not on a plain background.

A missing figure shows a placeholder (hidden on course cards). The server lists what
exists at `/figures.json`. The course-to-area mapping is `area()` in `../app.js`.

Prompt used (attach an existing figure as the style reference; fill in subject and pose):

> [SUBJECT]. Pose and camera: [POSE].
> Use the reference image ONLY for its drawing style: colours, proportions, grainy texture and
> face style. Do NOT copy its pose, composition, props or background elements.
> Clean modern editorial vector illustration of one Sri Lankan university student, confident and
> friendly, natural brown skin tone, simple happy face, slightly long limbs. Smart-casual clothes.
> Shading is neat and minimal: one darker flat shade on the shadow side of each garment,
> following real folds, no random blobs, no wavy or camouflage patterns. Subtle fine grain.
> Only the character, nothing else: no floating objects, no splashes, no swooshes, no sparkles,
> no ground. The only props are what the student holds or wears. Character centred with
> generous empty space around it. Flat colours only: no gradients, no shadows, no outlines, no
> text, no letters, no words, no logos. Plain solid #ECE4FD background filling the whole image.
> Clothing and props only in #C9B8F5 lavender, #4F6FE8 royal blue, #14185C navy, #F2B84B
> mustard, white, plus one lighter and one darker flat shade of each. Landscape 3:2, 1536×1024.

Dark copy (an edit of the finished image): "Same image, same drawing and colours. Change only
the background to plain solid #6880EE, filling the whole image, with no gradient or texture."

`how-results.png` was generated using the built-in imagegen tool with `signin.webp` as the
edit reference. Its full restoration prompt is saved in `how-results.prompt.txt`. The landing
preview and illustration use separate grid columns to prevent overlap. At very small sizes the
decorative preview is omitted so the illustration stays visible. The sign-in illustration is unchanged.

The same layout applies to all four landing steps. `how-checks.png` and `how-ask.png`
were restored using the built-in imagegen tool with their original `analysing.webp` and
`empty-chats.webp` references. Full prompts are in their matching `.prompt.txt` files.
Step 3 retains the existing high-resolution 1536×1024 engineering artwork, mirrored so
the bridge extends to the left. The wider 4:3 landing panel places each student on the left
and the preview on the right, with artwork capped at its previous rendered size. The chat step
instead centers the preview at the top and the reclining student at the bottom, in separate rows.
