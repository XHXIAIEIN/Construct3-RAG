# Design Tokens for the Tool Pages

Date: 2026-10-13

## Problem

Two pages carry the tool's own chrome rather than a game's: the recording
review page beside a preview recording
(`skills/construct3-agent-plugin/assets/recording-review.html`) and the API
playground (`src/interfaces/http/playground.html`). The review page had grown
a palette of one-off greys, type at three sizes with no weight discipline,
zebra-striped rows and borders drawn as full rules on every edge; the
playground removed its outlines without a `:focus-visible` in their place, so
a keyboard lost every focus, set type at 9 to 13px with no set, and drew
borders darker than their surface at 1.56:1, which is no border at all. The
user's verdict on the review page was that the layout and colour lacked
taste, and the ask named where to learn the rest: the host UI kits Anthropic
published.

Task: one token layer, declared once per theme, whose names are the host
kits', so that a page's look is a change of palette and a new page copies
names, not values, and no page invents a grey.

## Evidence

- Anthropic's MCP Apps UI kit, the Figma community file "MCP Apps for
  Claude", and the design guidelines at claude.com carry the naming:
  `--color-background-{primary,secondary,tertiary}`,
  `--color-text-{primary,secondary,tertiary}`, `--color-border-*`,
  `--color-accent` with `-text`, `-tint` and `-wash`,
  `--font-text-{xs,sm,md}-size`, `--font-weight-{normal,medium,semibold}`,
  `--border-radius-{sm,md,lg}`.
- `modelcontextprotocol/ext-apps`, `examples/basic-host/src/host-styles.ts`,
  holds the full table the host pages declare, which is where the tiered
  background, tiered border and accent family above were read.
- Anthropic's brand guidance is warm paper and ink with a coral accent,
  which gives the warm neutrals below their hue rather than a flat grey.
- The host application's own implementation, as read off its shipped styles
  and kept in the user's notes (Tailwind CSS, native `@keyframes` for the
  CPU-cheap animation, Framer Motion's spring model for the interactive):
  its two signature animations, its numerals practice and its clay
  `#d97757` are in "Motion" and rule 7 below. It is the same coral and the
  same standard easing this record carries, so the two agree by
  measurement, not by coincidence.
- The preview and watched values are read on these pages, not a game, so
  density matters: the review page holds a frame strip, a step list and
  watched values beside each other without shrinking their type, and its
  14/12/11px scale is the local answer to that.
- Contrast was measured per surface, not per token: the first pass left the
  faint text tokens at 2.44 to 3.53:1, below the 4.5:1 a text token owes,
  while the older template had been at 5.2 and 5.6. The faint was a
  regression, so each token was re-picked for its own surface and theme
  until the minimum on any surface it lands on was past 4.5:1.

## Decision

Both pages declare the tokens below; the review page declares light and
dark together, the playground is dark-only with the dark column of the
review page. The names are the host kits'. The values are this repository's:
where the host kits' scale and a dense tool disagree, the token keeps the
host kit's name and the local value, and that is the whole contract.

### Surfaces and text, light

| Token | Value | Used for |
|-------|-------|----------|
| `--color-background-primary` | `#faf9f5` | the page |
| `--color-background-secondary` | `#ffffff` | a panel, a card |
| `--color-background-tertiary` | `#f2f0e8` | an inset, a well, a track |
| `--color-text-primary` | `#141413` | body text, values |
| `--color-text-secondary` | `#6b6963` | notes, labels, metadata |
| `--color-text-tertiary` | `#77746d` | ruler ticks and frame numbers; 4.66:1 at worst, the faintest a text token may be |
| `--color-border-tertiary` | `#e7e4da` | the hairline a panel is ruled by |
| `--color-border-primary` | `#d6d2c5` | a panel's edge, a control's edge |

### Accents and semantic colours, light

| Token | Value | Used for |
|-------|-------|----------|
| `--color-accent` | `#d97757` | what is selected or marked |
| `--color-accent-text` | `#b85a3d` | accent as text, where 4.5:1 needs the darker step |
| `--color-accent-tint` | `#f6e8df` | a selection's wash |
| `--color-accent-wash` | `#faf0e9` | the lightest accent surface |
| `--color-info` | `#6a9bcc` | data marks |
| `--color-info-text` | `#3f6d9e` | a link, a copied note |
| `--color-info-tint` | `#e8eff7` | a data mark's surface |
| `--color-info-strong` | `#bcd2e8` | a stronger data mark |
| `--color-danger` | `#bf3a2b` | what failed |
| `--color-danger-tint` | `#f9e7e2` | the failed step's surface |
| `--color-stage` | `#000000` | the frame strip's stage; no host-kit counterpart |

### The dark palette

Declared under `@media (prefers-color-scheme: dark)`, same names, warm
charcoal instead of paper:

| Token | Value |
|-------|-------|
| `--color-background-primary` | `#171716` |
| `--color-background-secondary` | `#201f1e` |
| `--color-background-tertiary` | `#282826` |
| `--color-text-primary` | `#f2f0e9` |
| `--color-text-secondary` | `#a6a39a` |
| `--color-text-tertiary` | `#8b8981` on the review page, `#94928a` on the playground; each at or above 4.7:1 on every surface it lands on |
| `--color-border-tertiary` | `#2e2e2c` |
| `--color-border-primary` | `#3c3c39` |
| `--color-accent`, `--color-accent-text` | `#e08a6c` |
| `--color-accent-tint` | `#35241c` |
| `--color-accent-wash` | `#2c221b` |
| `--color-info`, `--color-info-text` | `#8fb3d9` |
| `--color-info-tint` | `#1e2937` |
| `--color-info-strong` | `#33506e` |
| `--color-danger` | `#e06a5c` |
| `--color-danger-tint` | `#38201b` |

The playground adds, for its own readers: `--color-accent-hover`
`#e08a6c`, `--color-border-secondary` `#4c4c47`, `--color-grid-dot`
`#262623`, `--color-success` `#7fc8a0` with `-tint` `#1e2f24` and
`-strong` `#2f6a44`, `--color-warning` `#e8c85a` with `-tint` `#35241c`,
`--color-danger-strong` `#7c332a`, and the syntax family
`--color-syntax-string` `#8fce9a`, `--color-syntax-number` `#c3aae8`,
`--color-syntax-bool` `#e8b48a`.

### Type, spacing, radii, motion

- Weights: `--font-weight-normal` 400, `--font-weight-medium` 500,
  `--font-weight-semibold` 600. Three, no others; a weight outside the set
  is a mistake, not a fourth tier.
- Sizes: the review page declares `--font-text-md-size` 14px,
  `--font-text-sm-size` 12px, `--font-text-xs-size` 11px; the playground
  adds `--font-text-lg-size` 13px and takes xs at 10px for its denser
  chrome. A page declares one scale and stays inside it; no 9px type.
- Families: `--font-sans` and `--font-mono`. The review page names IBM
  Plex with system fallbacks and loads nothing from the network, so the
  page opens offline as the recording does; a family name is a preference
  list, never a download.
- Spacing: the review page's single `--gap` 12px, one step between
  neighbours and two between groups. The playground keeps its 16px and 10px
  where the toolbar asks for them, and no page invents a fifth gap.
- Radii: `--border-radius-sm` 4px, `--border-radius-md` 6px,
  `--border-radius-lg` 8px. A closed set; a square corner is `0` on the
  same ladder, not outside it.
- Motion: the two families below, each whole or not at all; the pages
  declare the durations of the ordinary kind.
- Shadows: `--shadow-hairline` and `--shadow-sm` on the review page,
  `--shadow-card` and `--shadow-menu` on the playground; values scale with
  the theme's alpha.

### Motion

The host implementation runs two animation families, each on its own
duration and easing, and neither is a compromise between them:

| Family | Duration | Easing | What it does |
|--------|----------|--------|--------------|
| Reveal | 90ms | `cubic-bezier(.215, .61, .355, 1)` (easeOutQuart) | text arriving glyph by glyph: opacity 0 to 1 and `blur(6px)` to `blur(0)`, each glyph `calc(var(--i, 0) * 30ms)` after the one before it |
| Quiet | 1.9s, loop | `cubic-bezier(0.4, 0, 0.2, 1)` | the thinking indicator: three 3px dots in the clay accent `#d97757`, rising 2px and settling back, 0, 0.15s and 0.3s apart |

Both easings and the clay are values this record already carried, which is
the cross-check that the palette and the motion pacing here are the host's
own rather than a local invention: `--color-accent` `#d97757` and `--ease`
`cubic-bezier(0.4, 0, 0.2, 1)` are what the implementation uses, clay for
its quiet dots and standard easing for the loop that carries them.

Neither page has a state those families serve: no page streams text, so
there is no reveal to run, and no page thinks aloud, so there is no quiet
loop to placate. What the pages declare is the ordinary kind —
`--dur-1` 120ms, and `--dur-2` 180ms on the playground, on `--ease` — for
hover, selection and state changes. A page that later streams an answer
adopts the reveal family whole, at 90ms on its own curve and never on a
duration between the two, and a page that later waits adopts the quiet
family whole; a curve between them is neither and is refused. A transition
that does not tell the user something is removed, and
`@media (prefers-reduced-motion: reduce)` collapses all of it to 0.01ms
here, the pages' own fallback.

### Rules the two pages follow

1. A theme is a palette change. Light and dark are declared together, so
   dark is a second `:root` and never a second sheet to keep in step.
2. One accent marks what is selected; blue marks data and red marks what
   failed. The page's own marks use the accent, so a selection reads as
   this page's, and a failed step is the only red.
3. Rows are ruled by hairlines, not striped. `--color-border-tertiary`
   between rows and `--color-border-primary` at the edge; no zebra.
4. Keyboard focus is always visible:
   `:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }`.
   Removing an outline without this in its place is the defect the
   playground had, not a style.
5. Every text token owes 4.5:1 on each surface it lands on, measured per
   theme. A token that fails is re-picked or dropped; it is never kept
   because it looks faint.
6. The review page's template keeps its placeholder contract:
   `/*TIMELINE*/null` and `/*RECORDINGS*/null`, which
   `scripts/preview_project.py` replaces when it reads the template. The
   design language lives in the `<style>` alone; the DOM and the script are
   not part of it.
7. A numeral that changes while the user watches is tabular:
   `font-variant-numeric: tabular-nums`, which the host does for its 03:02
   clocks and its 1,024-token counts. The review page sets it on every
   number it shows — frame times, step lists, watched values — and the
   playground sets it on its latency, so a 337ms turning 200ms shifts
   digits rather than the line.

## Keeping the contract

- Before changing any UI, grep `docs/decisions/`. A visual rule written
  there is a contract, not a preference; when a change covers one, the
  record is revised in place with the reason and the evidence, as
  `docs/decisions/preview-player.md` was for this one.
- Renaming a token is not a find-and-replace. Use a boundary-aware pattern
  such as `(?<![a-z0-9-])--token(?![a-z0-9-])`, and do a compound name in a
  second pass, since `--accent-text` contains `--accent`; the review page's
  246 renames held rendering byte-for-byte by doing it this way and checking
  the definition and use sides.
- Grep `var(` over the whole file, not only the `<style>`: the playground
  referenced six old tokens from its script's inline styles, which a CSS
  block rename leaves broken.
- The template ships in two copies that are kept equal:
  `skills/construct3-agent-plugin/assets/` is the source and
  `plugin/skills/construct3-agent-plugin/assets/` is written by the build;
  change the source, then build or copy and diff.
- Verify a change the way this one was: `node --check` for the script, a
  computed-style probe that reads every declared token's resolved value,
  screenshots of every entry state in both themes through a real browser
  with no page errors, and the pytest suites that read the template
  (`tests/test_skill_preview_project.py`, `tests/test_skill_review_look.py`).
- A token nothing uses is deleted, not kept for later.

## Re-evaluate when

- The host kits publish a token this language is missing: take the name,
  keep the local value, and say which is which here.
- A page needs a fifth type size, a fourth weight or a radius outside the
  set: that page has outgrown the layer, and the answer is a reason in this
  record, not a value in the page.
- Contrast measurement moves to a per-token check that fails the build, so
  the audit that caught the faint tokens runs on every change rather than
  at review.
