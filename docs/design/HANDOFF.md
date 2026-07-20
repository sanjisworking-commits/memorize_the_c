# Constitution Memorizer — design handoff

Target repo: sanjisworking-commits/memorize_the_c (FastAPI + Jinja2 web layer in `src/constitution_memorizer/web/`).

## Files
- `Constitution Memorizer App.dc.html` — the approved interactive prototype (open in a browser). Single source of truth for layout, spacing, copy and behavior. All styles are inline on the elements — read values directly off the markup.
- `Constitution Memorizer.dc.html` — reference: mobile layout (390px) and unit-card anatomy for ARTICLE / CLAUSE / SUBCLAUSE.

## Design tokens
- Ink `#141414`, muted `#6b6b6b`, faint `#9a9a9a`, hairline `#dcdcdc`, page bg `#ececea`, paper `#fff`
- Accent (primary CTA + due markers): `#141414` (user default; alternates `#0E7569` teal, `#B42318` red). Red `#B42318` is ALSO the fixed destructive color (Reset).
- Fonts: Fraunces (display, 700) + Source Sans 3 (body). Square corners everywhere, 1px hairlines, no shadows except the outer sheet.

## Screens & behavior (all in the prototype)
1. **Home** — date, due lede, Continue card (next unit in chain), Due list (rows open that unit), quiet stats, red "Reset all progress".
2. **Learn** — session progress bar; unit badge + breadcrumb; sibling rail (clause chips / letter rail); six recall modes on the same unit text:
   Read · Cloze (tap-to-reveal blanks; density light/medium/heavy = hide words ≥8/≥6/≥4 letters) · Letters (first-letter initials ⇄ full text) · Type (textarea, per-word diff: gray = unreached, black = correct, red strikethrough = wrong) · Recite (blurred text, hold-to-peek; **Start/Stop** uses Web Speech API for spoken recall, then LCS accuracy map vs Bare Act — Chrome/Edge) · Card (flip title ⇄ text).
   Footer: accent "Done — next unit" (marks complete, advances chain), ghost "Again tomorrow", meta line, red "Reset unit".
3. **Choose** — split-capable clause with no preference: "Learn whole clause" (solid) vs "Split into letters" (outline). Preference persists (`split_preference` table).
4. **Calendar** — month grid; chips: solid black = memorized, gray = review done, accent-outline = due today, dashed = scheduled. Chips open the unit. Today cell ringed in accent.
5. **Progress** — 4 stat tiles, mastery map (one row per Part, one 16px cell per Article: new/learning/review/mastered/due; tracked cells clickable), tracked-articles list with completion bars.
6. **Browse** — Part index grid → Article reading view: every clause/letter row = mastery dot + verbatim text + "Learn" button (accent outline) or "Choose" for split-capable clauses without a preference; "Practice article" header CTA runs the article chain. **Amendment history** timeline (or quiet Unamended note) under the article; meta line includes amendment count. **Explain it back** (Sprint 22) free-text gloss below amendments.
7. **Learn footnote** — when curated, a faint `✦` one-liner under the unit subtitle explaining amendments / omitted letters (e.g. 19(1)(f)); does not change memorized text.

## Rules
- Bare Act text verbatim, never paraphrased (repo hard constraint).
- Chain/scheduling: existing ReminderEngine (1→3→7→14→30→60 day ladder); letters preference walks `letter_sequence_*` then resumes the global chain.
- Article 19(1)(f) omitted (repealed).
- Mobile: single column, bottom-fixed Again/Done bar (48px targets) — see reference file 1b.
