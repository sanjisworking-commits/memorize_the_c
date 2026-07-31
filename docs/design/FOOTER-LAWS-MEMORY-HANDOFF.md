# Footer, Home launcher, Relevant laws, Memory log & Settings — design handoff (Cursor)

Covers the additions made in this batch to the approved prototype (`Constitution Memorizer App.dc.html`). Same tokens as HANDOFF.md (ink `#141414`, muted `#6b6b6b`, faint `#9a9a9a`, hairlines `#dcdcdc`/`#e5e5e4`, accent teal/red, Fraunces display / Source Sans 3 body, square corners).

## 1. Nav declutter + footer

- **Top nav** is now only the scheduled core loop: Home · Learn · Calendar · Progress · Browse. Nothing else lives up there.
- **Footer** (full-width, `border-top: 1px solid #141414`, padding 14px 32px, flex space-between, wraps): on the left a row of text links — **Tables · Relevant laws · Memory log · Settings** (12.5px/600; active page = ink + underline, else muted). On the right, the **theme toggle** chip (moved out of the nav).
- Footer renders on every page.

## 2. Home → "Reference & tools" launcher

Below the Due list / How-to-use, above the stat+reset footer band.
- h2 "Reference & tools" (Fraunces 20px/700) + lede "Study aids that aren't on a schedule — open any time."
- Grid `repeat(auto-fill, minmax(200px,1fr))`, gap 8px. Three cards (ink border, white bg, hover `#f7f7f6`): **Tables**, **Relevant laws**, **Memory log** — each Fraunces 17px title + 12.5px muted sub, whole card opens the page.

## 3. Relevant laws (new — two screens)

Statutes mapped to the Articles they implement. Modelled exactly on Browse (list of cards → full detail screen; **no popups**).

### List (`page: 'laws'`, `data-screen-label="Relevant laws"`)
- h1 "Relevant laws" + lede.
- Grid of compact cards (same grid as Browse articles): law **name** (Fraunces 16px/700) + meta line `"{year} · {linked Article labels}"`. Whole card opens the detail screen.

### Detail (`page: 'lawDetail'`, `data-screen-label="Law detail"`)
- Header: eyebrow "RELEVANT LAWS", h1 law name (Fraunces 34px), year; a **"Practice all"** CTA (opens the first clause in Learn).
- Article chips: tracked Articles are ink/clickable (jump to that Article view), untracked are muted/inert.
- **Clause rows** (`border-top: 1px solid #141414`, rows `border-bottom: 1px solid #dcdcdc`, hover `#f7f7f6`): a status dot (filled ink when the clause unit is completed, else hollow), the clause text (`**{section ref}** — {body}`), and a **Learn / Review** button.
- "All laws" back button.

### Clauses are learnable units (key wiring)
- Every law clause is registered as a unit `id = "law{lawIndex}-{clauseIndex}"`, `kind: 'Law clause'`, with `text`, `next` (chains to the next clause in the same Act), `lawName`, `lawIndex`.
- Opening one enters the normal Learn flow: all six recall methods, the same Done-gating, completion, and reset behavior as an Article clause.
- Learn-view crumb for a law unit reads `"Relevant laws · {Act name} ({year})"` instead of the Part/Article crumb.
- Backend: laws + clauses are their own content collection; a clause unit joins the same `unit_progress` / scheduler tables as constitutional units (one unified unit model, distinguished by kind).

### Law seed data
Seven Acts live in the `lawList()` method — RTI (2005), RP Act (1951), Citizenship (1955), PCR (1955), RTE (2009), EP Act (1986), UAPA (1967) — each with `name`, `short` (Learn title prefix), `year`, linked `arts`, and `clauses [ref, text]`. Lift verbatim from there.

## 4. Memory log (new — general mind-palace scheduler)

A **separate** calendar from the Constitution scheduler, for memorising anything (lists, acronyms, mind-palace routes). `page: 'memory'`, `data-screen-label="Memory log"`.

### Log form
Two text inputs — title ("What did you memorise today?") + optional acronym/hook — and a **"Log for today"** CTA. Adds an entry dated today (prototype's fixed "today"), clears the form, selects the new entry.

### Calendar
- Month grid (7-col, weekday header row). Each logged entry places a **★ memorised** marker on its day and **review markers** at **+1, +3, +7, +14, +30** days.
- Marker states by date vs. today: memorised (ink), review **done** (grey, past), review **due** (accent-bordered, today), **scheduled** (dashed, future). Legend above the grid. Today's cell has an accent inset ring.
- Every marker is clickable → opens that entry's detail.

### Revision sheet + detail modal
- Full-width **Revision sheet** list under the calendar: each entry shows title, an acronym/next-review meta line, and a photo thumbnail if attached. Click opens the detail.
- **Detail is a centered modal** (overlay + click-outside / ✕ to close): title, acronym, the **1·3·7·14·30 schedule chips** (done ✓ / due / upcoming), the **revision-notes photo**, and an **Upload / Replace note photo** file input.
- **Photo notes**: uploaded via `<input type="file" accept="image/*">`, read with `FileReader` to a data URL, stored on the entry and rendered (thumbnail in the sheet, full image in the modal). Prototype keeps photos in memory for the session.
- Backend: entries = `{id, title, acronym, logged_date, photo}` per user; reviews derived from `logged_date + [1,3,7,14,30]`; photo stored as an uploaded asset (URL), not a data URL. Interval set is shared with the Constitution scheduler but tracked independently.
- Seeded with the user's UNESCO year-wise example + a Fundamental Duties entry.

## 5. Settings (new — `page: 'settings'`)

- **Appearance**: Auto / Light / Dark segmented buttons (Auto follows system live). Same persistence as the footer toggle (`cm-theme`).
- **Progress**: "Reset all progress" (red outline) — clears memorization + method tracking; written explanations are kept.

## 6. Where it lives in the prototype
- Template: Home `launchers` loop; `Relevant laws` + `Law detail` blocks; `Memory log` block (form, calendar `mlDays`, revision sheet `mlRows`, detail modal); `Settings` block; footer band (`footerLinks`, `themeToggle`).
- Logic: `lawList()` and law-clause registration inside `units()`; `lawCards`/`lawDetail`/`lawDetailRows`/`practiceLaw`/`lawBack`; Memory-log state (`logItems`, `mlSel`, `mlTitle`, `mlAcr`) with `mlAdd`/`onMlPhoto`/`mlClose` and the `mlDays`/`mlRows`/`mlDetail` derivations; `launchers`, `footerLinks`, `themeOptions` in `renderVals()`.
