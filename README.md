# Constitution Memorizer

Production-oriented tooling to help users **understand, revise and memorise the Constitution of India**.

Work proceeds in two layers:

1. **Corpus pipeline (Phase 1–2)** — deterministic PDF → structured JSON for the Bare Act
2. **Learning layer (Sprints 1–25)** — Learning Units, progress, reminders, and a web UI aligned to the design prototype

Each sprint ships on its **own git branch** and updates this README so documentation stays in sync with merged capability.

| Layer | Branch pattern | Status |
|-------|----------------|--------|
| Phase 1 | `cursor/constitution-pdf-pipeline-1a75` | Done |
| Phase 2 | `cursor/phase-2-parser-hardening-1a75` | Done |
| Sprint 1 | `cursor/sprint-1-learning-unit-generator-1a75` | Done |
| Sprint 2 | `cursor/sprint-2-alphabetic-fallback-1a75` | Done |
| Sprint 3 | `cursor/sprint-3-sqlite-scheduler-1a75` | Done |
| Sprint 4 | `cursor/sprint-4-learn-home-ui-1a75` | Done |
| Sprint 5 | `cursor/sprint-5-browse-search-progress-1a75` | Done |
| Sprint 6 | `cursor/sprint-6-design-tokens-1a75` | Done |
| Sprint 7 | `cursor/sprint-7-sheet-nav-1a75` | Done |
| Sprint 8 | `cursor/sprint-8-home-screen-1a75` | Done |
| Hotfix | `cursor/fix-articles-1-2-1a75` | Done |
| Hotfix | `cursor/fix-browse-artefacts-1a75` | Done |
| Hotfix | `cursor/fix-articles-44-45-1a75` | Done |
| Hotfix | `cursor/corpus-artefact-sweep-1a75` | Done |
| Sprint 9 | `cursor/sprint-9-choose-incomplete-1a75` | Done |
| Sprint 10 | `cursor/sprint-10-learn-read-1a75` | Done |
| Sprint 11 | `cursor/sprint-11-sibling-rails-1a75` | Done |
| Sprint 12 | `cursor/sprint-12-again-tomorrow-1a75` | Done |
| Sprint 13 | `cursor/sprint-13-learn-card-1a75` | Done |
| Sprint 14 | `cursor/sprint-14-learn-cloze-1a75` | Done |
| Sprint 15 | `cursor/sprint-15-learn-letters-1a75` | Done |
| Sprint 16 | `cursor/sprint-16-learn-type-1a75` | Done |
| Sprint 17 | `cursor/sprint-17-learn-recite-1a75` | Done |
| Sprint 18 | `cursor/sprint-18-recite-voice-1a75` | Done |
| Hotfix | `cursor/fix-articles-365-plus-1a75` | Done |
| Sprint 19 | `cursor/sprint-19-calendar-1a75` | Done |
| Sprint 20 | `cursor/sprint-20-progress-mastery-1a75` | Done |
| Sprint 21 | `cursor/sprint-21-amendment-history-1a75` | Done |
| Sprint 22 | `cursor/sprint-22-explain-it-back-1a75` | Done |
| Sprint 23 | `cursor/sprint-23-mac-packaging-1a75` | Done |
| Sprint 24 | `cursor/sprint-24-study-reminders-1a75` | Done |
| Sprint 25 | `cursor/sprint-25-mac-install-backup-1a75` | Done |

**Hard constraint:** the learning layer must **not** modify `data/output/constitution.reviewed.json`, Docling output, the parser, or corrections modules.

---

## Corpus pipeline (Phase 1–2)

### Phase 1 — PDF → JSON

- Project foundation (Python package, CLI, configuration)
- PDF extraction with [Docling](https://github.com/docling-project/docling)
- Conservative text normalisation (artefact repair only)
- Constitution-specific parsing into schema-validated JSON
- Validation and extraction reports
- Pytest coverage for the parsing pipeline

### Phase 2 — Corpus review / parser hardening

- Structural boundary hardening (CONTENTS, schedules, appendices)
- Duplicate Article demotion with audit events
- Schedule recovery (including glued Docling headings)
- Footnote association pass (no invented links)
- Structure expectations (`data/expected/structure_expectations.json`)
- External correction overlay (`data/corrections/corrections.json`)
- Corpus review report CLI
- Regression fixtures from real Markdown failures

---

## Learning layer (Sprints)

The learning layer reads `constitution.reviewed.json` and produces schedulable **Learning Units**. Users will eventually choose whether to learn a numbered clause as a whole or as letter subclauses `(a)(b)…` — the generator emits both paths; preference persistence starts in Sprint 3.

### Sprint 1 — Generator core ✅

**Branch:** `cursor/sprint-1-learning-unit-generator-1a75`

- Package `src/constitution_memorizer/learning/`
  - `schemas.py` — `LearningUnit`, `LearningUnitType`, `LearningUnitsDocument`
  - `time_difficulty.py` — word-count learning time + difficulty 1–5
  - `learning_unit_generator.py` — unit emission + revision chain
- Unit types: `ARTICLE`, `CLAUSE`, `PART_OVERVIEW`, `SCHEDULE_ENTRY`
- Rules: no clauses → one `ARTICLE`; numbered clauses → one `CLAUSE` each; schedules → entries or whole-body fallback; part overviews
- Fills `previous_unit` / `next_unit` / `revision_order` / tags / time / difficulty
- CLI: `generate-units`
- Fixture tests under `tests/fixtures/learning/`

**Out of scope in Sprint 1:** alphabetic dual units, text fallback, SQLite, UI.

### Sprint 2 — Alphabetic dual units + text fallback ✅

**Branch:** `cursor/sprint-2-alphabetic-fallback-1a75`

- When a clause has alphabetic children `(a)(b)…`, emit **both**:
  - parent `CLAUSE` (`allows_letter_split=true`, `child_unit_ids`)
  - child `SUBCLAUSE` units (`parent_clause_id`, `letter_sequence_next/prev`)
- Default global revision chain stays **clause-level** (SUBCLAUSE units are off-path until a letter preference exists)
- Roman `(i)(ii)` under a letter stay inside the parent SUBCLAUSE (no deeper split)
- Deterministic flat-body splitter (`text_fallback_splitter.py`) for Articles with empty `clauses` but markers in `body_text`
- Generated artefact: `data/output/learning_units.json` (+ `.min.json`)

**Real corpus snapshot (this repo):** 930 units — PART_OVERVIEW 19, ARTICLE 176, CLAUSE 479, SUBCLAUSE 225, SCHEDULE_ENTRY 31; 123 clauses allow letter split.

**Out of scope in Sprint 2:** UI choice screen, SQLite preference persistence.

### Sprint 3 — SQLite progress + reminder engine ✅

**Branch:** `cursor/sprint-3-sqlite-scheduler-1a75`

- Package `src/constitution_memorizer/progress/`
  - `db.py` — SQLite open + schema
  - `repository.py` — progress + `split_preference` CRUD
  - `scheduler.py` — `ReminderEngine` (`mark_done`, `due_today`, `stats`, next-unit resolution)
- Tables in `data/progress/progress.db` (local; gitignored except directory placeholder):

```sql
learning_unit_progress(
  learning_unit_id, status, times_completed, last_completed,
  next_revision, interval_days, ease_factor, created_at, updated_at
)
split_preference(
  parent_clause_id, mode CHECK IN ('whole','letters'), updated_at
)
```

- Statuses: `new` → `review` → `mastered`
- Interval ladder: `1 → 3 → 7 → 14 → 30 → 60` days; completing at 60 → `mastered`
- Default split mode is **whole** (clause-level `next_unit`); `letters` walks `letter_sequence_*` then resumes the global chain
- `next_to_learn_from_clause(parent_id)` — entry point after a future Choose-screen preference
- Tests: `tests/test_reminder_engine.py` (temp DB only; no HTTP)

**Out of scope in Sprint 3:** FastAPI / templates.

### Example (library API)

```python
from datetime import date
from constitution_memorizer.progress import ReminderEngine

engine = ReminderEngine.from_paths(
    "data/progress/progress.db",
    "data/output/learning_units.json",
)
engine.set_split_preference("article-25-clause-2", "letters")
result = engine.mark_done("article-25-clause-2-subclause-a", as_of=date.today())
print(result.progress.interval_days, result.next_unit_id)
print(engine.due_today())
print(engine.stats())
```

### Sprint 4 — Core learning UI ✅

**Branch:** `cursor/sprint-4-learn-home-ui-1a75`

- Package `src/constitution_memorizer/web/` — FastAPI + Jinja2 + static CSS/JS
- Routes:
  - `GET /` — Home checklist (due units + continue; respects split preferences)
  - `GET /learn/{unit_id}` — Learn card (redirects to choose when needed)
  - `POST /learn/{unit_id}/done` — mark done → next unit
  - `GET/POST /learn/{clause_id}/choose` — whole vs letters interstitial
  - `POST /learn/{unit_id}/reset` / `POST /reset` — red reset controls
  - `/browse`, `/search`, `/progress` — Sprint 5 stubs
- Design: monochrome paper UI; **green** Done / Learn whole; **green outline** Split into letters; **red** Reset
- CLI: `serve`
- Deps: `fastapi`, `uvicorn`, `jinja2`, `python-multipart` (+ `httpx` for tests)
- Tests: `tests/test_web_app.py`

**Out of scope in Sprint 4:** full Browse / Search / Progress pages.

### Serve the learning UI

Requires `data/output/learning_units.json` (from `generate-units`).

```bash
python -m constitution_memorizer.cli serve \
  --host 127.0.0.1 \
  --port 8001 \
  --output-dir data
```

Optional paths: `--units`, `--db`, `--reviewed`.

Then open `http://127.0.0.1:8001/`.

| Path | Role |
|------|------|
| `data/output/learning_units.json` | Schedulable units (tracked) |
| `data/output/constitution.reviewed.json` | Browse source (read-only; local) |
| `data/progress/progress.db` | Progress + split preferences (local) |

UI entry points: `/` Home · `/browse` · `/search` · `/progress` · `/learn/{id}`.

### Sprint 5 — Browse / Search / Progress ✅

**Branch:** `cursor/sprint-5-browse-search-progress-1a75`

- **Browse** — `GET /browse`, `GET /browse/article/{number}`  
  Full Article text from `constitution.reviewed.json` + Learn CTAs for that Article’s units  
  Article cards also expose **← previous / next →** links in Browse order
- **Search** — `GET /search?q=`  
  - `20` → browse Article  
  - `20(2)` → learn clause (or Choose if split-capable and unset)  
  - `19(1)(a)` / `25(2)(a)` → set `letters` preference on parent, open subclause
- **Progress** — `GET /progress`  
  Unit totals by type; Article completion % from the chosen whole/letters path
- Final metrics: [`docs/learning-layer-report.md`](docs/learning-layer-report.md)
- Tests: `tests/test_web_sprint5.py`

### Sprint 6 — Design tokens ✅

**Branch:** `cursor/sprint-6-design-tokens-1a75`

- Design prototypes checked into [`docs/design/`](docs/design/) (interactive App, anatomy/mobile reference, HANDOFF, `support.js`)
- CSS tokens match HANDOFF: ink `#141414`, muted `#6b6b6b`, faint `#9a9a9a`, hairline `#dcdcdc`, page `#ececea`, paper `#fff`, accent `#141414`, destructive `#B42318`
- Flat page background (no cream gradients); square corners; primary CTAs use ink accent (legacy `.btn-green` aliases to accent)
- Fraunces + Source Sans 3 unchanged; **no route or layout changes** (sheet chrome / Home restyle = Sprint 7–8)

### Sprint 7 — Sheet chrome + navigation ✅

**Branch:** `cursor/sprint-7-sheet-nav-1a75`

- Outer paper **sheet** (max 980px, 1px border, light shadow) wrapping all pages
- Header nav: **Home · Browse · Calendar · Progress · Search** with active ink pill
- `GET /calendar` stub (full month grid in Sprint 19)
- Search page restyled to the same sheet tokens (`btn-accent`)
- Tests: `tests/test_web_sprint7.py`

### Sprint 8 — Home screen ✅

**Branch:** `cursor/sprint-8-home-screen-1a75`

- Prototype Home layout: date eyebrow, “Today” title, due lede
- Continue card (kind + meta + Continue CTA) or “All caught up” empty state
- Due list with accent status dots; quiet stats line; text “Reset all progress”
- Helpers: `home_lede`, `unit_type_label`, `earliest_upcoming_revision` in `web/service.py`
- Tests: `tests/test_web_sprint8.py`

### Sprint 9 — Choose + incomplete panels ✅

**Branch:** `cursor/sprint-9-choose-incomplete-1a75`

- Choose screen matches prototype: Split choice eyebrow, solid / outline CTAs (`btn-accent`), remembered-choice note
- New `incomplete.html` panel (design tokens) for future readiness gating — reasons list, Browse/Home links
- Tests: `tests/test_web_sprint9.py`

### Sprint 10 — Learn Read anatomy ✅

**Branch:** `cursor/sprint-10-learn-read-1a75`

- Learn **Read** mode: session bar, type badge (Article/Clause/Subclause), Part crumb, Fraunces title, verbatim body, meta line
- Mode tab strip (Read active; other modes disabled until later sprints)
- Ink **Done — next unit** + text Reset unit; **Again tomorrow** (Sprint 12)
- Tests: `tests/test_web_sprint10.py`

### Sprint 11 — Sibling rails + subclause stem ✅

**Branch:** `cursor/sprint-11-sibling-rails-1a75`

- Clause sibling chips under the title when an article has multiple clauses
- Letter rail for `SUBCLAUSE` units (current / done / idle states)
- Gray parent stem above letter text (Bare Act wording with letter bodies removed)
- CTA becomes **Done — next letter** while a letter sequence continues
- Tests: `tests/test_web_sprint11.py`

### Sprint 12 — Again tomorrow + mobile sticky footer ✅

**Branch:** `cursor/sprint-12-again-tomorrow-1a75`

- Ghost **Again tomorrow** defers the unit to tomorrow without advancing the mastery ladder, then moves to the next unit
- Learn footer: Done + Again (+ meta + Reset); mobile sticky bar with 48px **Again** / **Done** targets
- Engine: `ReminderEngine.defer_until_tomorrow`
- Tests: `tests/test_web_sprint12.py`

### Sprint 13 — Learn Card ✅

**Branch:** `cursor/sprint-13-learn-card-1a75`

- **Card** recall mode: tap to flip between title face and verbatim Bare Act text
- Front: kind badge, display title, subtitle, “Recite it, then tap to check”
- Back: unit text + “Tap to flip back”
- Mode tabs: Read + Card enabled; Cloze / Letters / Type / Recite still disabled
- Subclause stem stays in Read only (hidden in Card, matching the design prototype)
- Client JS in `static/app.js` switches modes and resets flip on mode change
- Tests: `tests/test_web_sprint13.py`

### Sprint 14 — Learn Cloze ✅

**Branch:** `cursor/sprint-14-learn-cloze-1a75`

- **Cloze** recall mode: tap-to-reveal blanks over Bare Act wording
- Density **light / medium / heavy** hides words with letter-length ≥ **8 / 6 / 4**
- Controls: Reveal all, Hide again; status `N of M revealed — tap a blank`
- Blank style: transparent text + 2px ink underline; revealed: accent + weight 600
- Subclause stem shows in Cloze (hidden only on Card)
- Mode tabs: Read + Cloze + Card; Letters / Type / Recite still disabled
- Tests: `tests/test_web_sprint14.py`

### Sprint 15 — Learn Letters ✅

**Branch:** `cursor/sprint-15-learn-letters-1a75`

- **Letters** recall mode: first-letter initials ⇄ full Bare Act text
- Default shows monospace initials (first letter + kept `.,;—()` punctuation), en-space separated
- Toggle: **Show full text** / **Back to initials**; hint “Recite from the initials, then check yourself.”
- Subclause stem shows in Letters (hidden only on Card)
- Mode tabs: Read + Cloze + Letters + Card; Type / Recite still disabled
- Tests: `tests/test_web_sprint15.py`

### Sprint 16 — Learn Type ✅

**Branch:** `cursor/sprint-16-learn-type-1a75`

- **Type** recall mode: textarea from memory with live per-word diff
- Diff colors: gray = unreached, ink = correct, red strikethrough = wrong
- Stats: `N / M words · K correct` (punctuation-insensitive normalize)
- Subclause stem shows in Type (hidden only on Card)
- Mode tabs: Read + Cloze + Letters + Type + Card; Recite still disabled
- Tests: `tests/test_web_sprint16.py`

### Sprint 17 — Learn Recite ✅

**Branch:** `cursor/sprint-17-learn-recite-1a75`

- **Recite** recall mode: Bare Act text blurred by default; hold-to-peek clears blur
- Controls: **▸ Start reciting** / **■ Stop reciting** (accent ↔ destructive), **Hold to peek**
- Hint: “Recite aloud with the text hidden.”
- All six recall modes enabled (Read · Cloze · Letters · Type · Recite · Card)
- Tests: `tests/test_web_sprint17.py`

### Sprint 18 — Recite voice accuracy ✅

**Branch:** `cursor/sprint-18-recite-voice-1a75`

- Recite uses the browser **Web Speech API** (Chrome/Edge) to capture spoken recall
- Live transcript while listening; on Stop, LCS-align transcript vs Bare Act tokens
- Accuracy map: hit = ink, miss = gray; stats `N / M recalled · P%`; extras line for unmatched heard words
- Shared align helper: `web/recall_align.py` + `static/recall_align.js` (Type can reuse later)
- Unsupported / mic denied / **network** (speech cloud unreachable): clear message + manual “type what you recited” fallback with Check accuracy
- No server-side audio storage
- Tests: `tests/test_recall_align.py`, `tests/test_web_sprint18.py`

### Sprint 19 — Calendar month grid ✅

**Branch:** `cursor/sprint-19-calendar-1a75`

- `GET /calendar?year=&month=` renders a Sunday-first month grid (Prev / Today / Next)
- Chips from progress rows: solid black = memorized, gray = review done, accent outline = due, dashed = scheduled
- Scheduled chips project the **remaining** spaced-repetition ladder (1 → 3 → 7 → 14 → 30 → 60) from `next_revision`, assuming on-time completion
- Chips link to `/learn/{unit_id}`; today cell has an accent ring
- Best-effort history (current progress row only — no event log); legend + month summary
- Tests: `tests/test_web_sprint19.py`

### Sprint 20 — Progress mastery map ✅

**Branch:** `cursor/sprint-20-progress-mastery-1a75`

- `/progress` matches the prototype: 4 stat tiles, mastery map, tracked-articles list
- Mastery map: one row per Part from reviewed JSON; 16px Article cells (`new` / `learning` / `review` / `mastered` / `due`)
- Tracked cells link into Learn/Choose; tracked rows show completion bars and status tags
- States: mastered (all complete past 1-day) · learning (all complete on 1-day rung) · due (continue pointer) · review (partial) · new
- Tests: `tests/test_web_sprint20.py`

### Sprint 21 — Amendment history ✅

**Branch:** `cursor/sprint-21-amendment-history-1a75`

- Curated seed `data/reference/amendments.seed.json` for Arts 14 / 15 / 19 / 21
- Browse: Amendment history timeline (or quiet Unamended line) + meta line with amendment count
- Learn: `✦` footnote under the subtitle when a hand-quality `learn_note` exists
- Read-only context; memorized text remains current Bare Act wording
- Tests: `tests/test_web_sprint21.py`

### Sprint 22 — Explain it back ✅

**Branch:** `cursor/sprint-22-explain-it-back-1a75`

- Browse article: “Explain it back” free-text gloss under amendments (every article)
- Debounced autosave (~500ms) to SQLite `article_gloss`; Clear deletes the row
- Survives Reset unit / Reset all progress; never affects mastery or scheduling
- Per-article placeholders in `data/reference/gloss_placeholders.seed.json`
- Tests: `tests/test_web_sprint22.py`

### Sprint 23 — Mac packaging and auto-start ✅

**Branch:** `cursor/sprint-23-mac-packaging-1a75`

- `scripts/mac/start-ui.command` / `stop-ui.sh` for local serve on port 8001
- LaunchAgent template + `install-serve-agent.sh` / `uninstall-serve-agent.sh` (start UI at login)
- README daily-driver section; progress remains in `data/progress/progress.db`

### Sprint 24 — Study reminders (ntfy) ✅

**Branch:** `cursor/sprint-24-study-reminders-1a75`

- CLI `send-reminders` builds today’s due digest from `due_checklist` (Home parity)
- Channels: `console` (dry-run) and `ntfy` (`NTFY_TOPIC` / optional server + token)
- Skips send when nothing is due; morning LaunchAgent at 07:00
- Tests: `tests/test_reminder_digest.py`, `tests/test_send_reminders_cli.py`

### Sprint 25 — One install path + data durability ✅

**Branch:** `cursor/sprint-25-mac-install-backup-1a75`

- `scripts/mac/bootstrap.sh` — idempotent venv + `requirements-ci.txt` + editable install; `correct` / `generate-units` only if units missing
- `scripts/mac/install-all-agents.sh` — serve + reminders LaunchAgents together
- `scripts/mac/backup-progress.sh` — copy `progress.db` to `~/Documents/ConstitutionMemorizerBackups/`
- Optional weekly backup LaunchAgent (`install-backup-agent.sh`)
- README: first Mac setup, what survives reboot, restore, smoke checklist

### Hotfix — Browse / Learn corpus artefacts ✅

**Branch:** `cursor/fix-browse-artefacts-1a75`

- **Article 201:** cleared duplicated `opening_text` so Browse/Learn no longer repeat the first sentence
- **Article 124:** restored Bare Act clauses (1)–(7); removed `<!-- formula-not-decoded -->`, private-use glyphs, and footnote debris
- **20B / 20BA / 20BB / 20C:** Sixth Schedule paragraphs mis-parsed as Articles — `exclude` in corrections removes them from reviewed corpus, units, and Browse
- Corrections overlay gains `exclude: true`; regenerate with `correct --force` then `generate-units --force`
- Tests: `tests/test_browse_artefact_corrections.py`

### Hotfix — Articles 365–395 ✅

**Branch:** `cursor/fix-articles-365-plus-1a75`

- Restored truncated/glued titles and bodies for **366–369, 371E, 372, 376–378, 394**
- Created missing Part XXI/XXII articles: **370, 371, 371A–371D, 371F–371J, 372A, 393, 394A**
- Normalized omitted **379–391** bodies to `[Omitted.]` (clears footnote junk on 383)
- Source text taken from intermediate Markdown; regenerate with `correct --force` then `generate-units --force`
- Tests: `tests/test_articles_365_plus_corrections.py`

### Hotfix — Articles 44 / 45 ✅

**Branch:** `cursor/fix-articles-44-45-1a75`

- **Article 44:** amendment footnote had glued Art 45 onto the Uniform civil code sentence — stripped to Bare Act only
- **Article 45:** Seventh Schedule “Land revenue…” + `formula-not-decoded` debris replaced the DPSP article — restored early-childhood-care text and Part IV
- Tests: `tests/test_articles_44_45_corrections.py`

### Hotfix — Corpus artefact sweep ✅

**Branch:** `cursor/corpus-artefact-sweep-1a75`

- Global scrub in `apply_corrections`: strip `<!-- formula-not-decoded -->`, private-use glyphs, dash debris; clear `opening_text` that duplicates/prefixes `body_text` (fixes mass Browse/Learn repetition)
- Exclude more schedule mis-parses (Sixth/Seventh Schedule entries posing as Articles)
- Restore real Articles **71, 131, 150, 230** (and omitted **257A**) overwritten by schedule list junk
- Browse/unit builders also skip redundant openings as defense in depth
- Tests: `tests/test_corpus_artefact_scrub.py`
- Regenerate: `correct --force` then `generate-units --force`

### Split-choice behaviour (summary)

1. Opening a split-capable clause with no preference → **Choose** screen  
2. **Learn whole clause** → store `split_preference.mode = whole`; study the parent `CLAUSE`  
3. **Split into letters** → `mode = letters`; study `SUBCLAUSE` children via `letter_sequence_*`  
4. Search to a letter unit also sets `letters` and deep-links into that subclause  
5. Home due list / continue respect the chosen path  

---


## Why exact legal text is preserved

The Bare Act wording is authoritative. The pipeline:

1. Keeps Docling’s raw extraction separate from normalised lines and structured JSON
2. Never silently rewrites, paraphrases or “beautifies” legal text
3. Records normalisation and parsing decisions as audit events
4. Retains unclassified content instead of dropping it

Editorial metadata, simplified explanations and memorisation aids must remain separate from Bare Act text. Learning Units quote Bare Act wording; they do not replace it.

## Requirements

- Python **3.10+** (developed against 3.12)
- Dependencies listed in `requirements.txt` / `pyproject.toml` (`docling`, `pydantic`, `rapidfuzz`, `fastapi`, `uvicorn`, `jinja2`, `pytest`, `httpx`)

## Installation

Needs **Python 3.10+** (3.9 will fail with `requires a different Python`).

```bash
python3.12 -m venv .venv          # or: python3 -m venv .venv  if that is 3.10+
source .venv/bin/activate         # Windows: .venv\Scripts\activate
python --version                  # must show 3.10 / 3.11 / 3.12 …
python -m pip install --upgrade pip
pip install -r requirements-ci.txt   # learning UI + tests (no Docling)
pip install -e .
```

For the full PDF pipeline you need `pip install -r requirements.txt` instead (heavier).

### First Mac setup (daily driver)

Everyday use is a local server on **port 8001**. Learning data lives in SQLite on disk and survives shutdowns.

**One path** (from the repo root that contains `pyproject.toml`):

```bash
cd /path/to/memorize_the_c
git checkout main && git pull
chmod +x scripts/mac/*.sh scripts/mac/*.command
bash scripts/mac/bootstrap.sh
```

`bootstrap.sh` creates `.venv` if needed, installs `requirements-ci.txt` + the package, and runs `correct` / `generate-units` only when `data/output/learning_units.json` is missing.

**Start the UI** (pick one):

```bash
# Terminal
source .venv/bin/activate
python -m constitution_memorizer.cli serve --host 127.0.0.1 --port 8001

# Or double-click in Finder:
open scripts/mac/start-ui.command
```

Bookmark **http://127.0.0.1:8001/**.  
**Stop:** `Ctrl+C`, or `bash scripts/mac/stop-ui.sh`.

**Install both LaunchAgents** (UI at login + morning reminders):

```bash
# Subscribe in the ntfy app to the same topic first
export NTFY_TOPIC=cm-yourname-study
bash scripts/mac/install-all-agents.sh
```

Or install separately: `install-serve-agent.sh` / `install-reminders-agent.sh`.  
Unload: `uninstall-serve-agent.sh` / `uninstall-reminders-agent.sh`.  
Logs: `~/Library/Logs/constitution-memorizer-*.log`.

### Study reminders (ntfy)

Daily push of today’s due units (same list as Home). Does **not** require the UI server to be running.

1. Install the [ntfy](https://ntfy.sh/) app and subscribe to a private topic, e.g. `cm-yourname-study`.
2. Test from the repo:

```bash
source .venv/bin/activate
export NTFY_TOPIC=cm-yourname-study
python -m constitution_memorizer.cli send-reminders --channel console --dry-run
python -m constitution_memorizer.cli send-reminders --channel ntfy
```

3. Prefer `install-all-agents.sh` (above), or:

```bash
export NTFY_TOPIC=cm-yourname-study
bash scripts/mac/install-reminders-agent.sh
```

Optional env: `NTFY_SERVER` (default `https://ntfy.sh`), `NTFY_TOKEN`, `REMINDER_BASE_URL`.  
Empty due lists skip the send.

### What survives reboot

| Asset | Survives power-off? | Notes |
|-------|---------------------|-------|
| `data/progress/progress.db` | Yes | Mastery, schedule, glosses (Explain it back) |
| `data/output/learning_units.json` | Yes | Regenerate with `generate-units` if missing |
| LaunchAgents | Yes | Under `~/Library/LaunchAgents/` |
| ntfy subscription | On phone | Topic secret in env / plist `EnvironmentVariables` |

**Backup** (manual or weekly agent):

```bash
bash scripts/mac/backup-progress.sh
# → ~/Documents/ConstitutionMemorizerBackups/progress-YYYYMMDD.db

# Optional Sunday 09:00 LaunchAgent:
bash scripts/mac/install-backup-agent.sh
```

**Restore:** stop the UI, then `cp ~/Documents/ConstitutionMemorizerBackups/progress-YYYYMMDD.db data/progress/progress.db`.  
Time Machine also covers the repo (and Documents backups) if those paths are included.

### Smoke checklist (Mac daily driver)

1. Login → UI responds at http://127.0.0.1:8001/ (serve LaunchAgent)
2. Morning → ntfy digest lists today’s due units (or silent if nothing due)
3. Study a unit → progress updates in the UI
4. `bash scripts/mac/backup-progress.sh` → file appears under Documents backups
5. Reboot → same progress and glosses still present (same `progress.db`)

### Try a sprint branch on your Mac (step by step)

Example: **Sprint 6** design tokens ([PR #10](https://github.com/sanjisworking-commits/memorize_the_c/pull/10)).

1. Open Terminal and go to your clone (the folder that contains `pyproject.toml`):

```bash
cd /Users/sanjwork/Desktop/MemorizeTheC/memorize_the_c/memorize_the_c
```

2. Activate the venv (recreate it with Python 3.12 if you still have 3.9):

```bash
source .venv/bin/activate
python --version
```

3. Fetch and check out the sprint branch:

```bash
git fetch origin
git checkout cursor/sprint-6-design-tokens-1a75
git pull origin cursor/sprint-6-design-tokens-1a75
```

4. Re-install the package (needed after switching branches):

```bash
pip install -r requirements-ci.txt
pip install -e .
```

5. Run regression tests (**required before merging any sprint into `main`**):

```bash
python -m pytest -m "not integration" -q
```

All tests must pass. If anything fails, do not merge.

6. Start the learning UI (this project uses **port 8001** by default in these docs):

```bash
python -m constitution_memorizer.cli serve --host 127.0.0.1 --port 8001
```

7. In your browser open: **http://127.0.0.1:8001/**

You should see a flat grey page background (`#ececea`), a white paper sheet, and **black** nav / Done buttons (not green). Stop the server with `Ctrl+C` in the Terminal.

If port 8001 is busy, pick another free port (e.g. `--port 8002`) and open that URL instead.

### Merge gate (every sprint)

Before merging a sprint PR into `main`:

1. `python -m pytest -m "not integration" -q` — must be green  
2. Spot-check the UI against that sprint’s scope (Sprint 6 = tokens only)  
3. Then merge the PR on GitHub  

Do not start the next sprint until the previous one is merged (or explicitly stacked).

## Place the Bare Act PDF

Copy or link your Bare Act PDF to:

```text
data/input/constitution_bare_act.pdf
```

A source PDF may already exist in this repository. Most generated artefacts under `data/raw`, `data/intermediate`, `data/output` and `data/rejected` are gitignored; **`learning_units.json`** is tracked as a learning-layer artefact.

## Commands

### Extract (Docling)

```bash
python -m constitution_memorizer.cli extract \
  --pdf data/input/constitution_bare_act.pdf \
  --output-dir data \
  --force
```

### Normalise

```bash
python -m constitution_memorizer.cli normalize \
  --input data/intermediate/constitution.md \
  --output-dir data \
  --force
```

### Parse

```bash
python -m constitution_memorizer.cli parse \
  --input data/intermediate/normalized_lines.json \
  --output-dir data \
  --force
```

### Validate

```bash
python -m constitution_memorizer.cli validate \
  --input data/output/constitution.json \
  --output-dir data \
  --force
```

### Full pipeline

```bash
python -m constitution_memorizer.cli pipeline \
  --pdf data/input/constitution_bare_act.pdf \
  --output-dir data \
  --force \
  --verbose
```

### Apply corrections overlay (Phase 2)

Corrections never mutate `data/raw/` or intermediate Markdown. They produce a reviewed twin:

```bash
python -m constitution_memorizer.cli correct \
  --input data/output/constitution.json \
  --corrections data/corrections/corrections.json \
  --output-dir data \
  --force
```

Output: `data/output/constitution.reviewed.json`

### Corpus review report (Phase 2)

```bash
python -m constitution_memorizer.cli review-report \
  --input data/output/constitution.json \
  --output-dir data \
  --force
```

Output: `data/output/corpus_review_report.json`

### Generate learning units (Sprints 1–2)

Requires `data/output/constitution.reviewed.json` (from `correct`). Does not modify the reviewed corpus.

```bash
python -m constitution_memorizer.cli generate-units \
  --input data/output/constitution.reviewed.json \
  --output data/output/learning_units.json \
  --output-dir data \
  --force
```

Also writes `data/output/learning_units.min.json` and prints unit-type counts.

Shared flags: `--force` / `--overwrite`, `--verbose`, `--output-dir`, `--config`.

## Output files

| Path | Description |
|------|-------------|
| `data/raw/constitution_docling.json` | Lossless Docling export |
| `data/raw/extraction_metadata.json` | Extraction metadata (hash, pages, versions) |
| `data/intermediate/constitution.md` | Docling Markdown |
| `data/intermediate/normalized_lines.json` | Normalised lines + keep/remove flags |
| `data/intermediate/parsing_events.json` | Normalisation and parser audit events |
| `data/output/constitution.json` | Structured, human-readable Constitution JSON |
| `data/output/constitution.min.json` | Minified twin of the above |
| `data/output/extraction_report.json` | Counts, warnings and errors |
| `data/output/constitution.reviewed.json` | Correction-overlay result (Phase 2) — **read-only for learning** |
| `data/output/corpus_review_report.json` | Human-review summary (Phase 2) |
| `data/output/learning_units.json` | Learning Units document (Sprints 1–2; tracked) |
| `data/output/learning_units.min.json` | Minified twin of learning units |
| `data/progress/progress.db` | SQLite progress + split preferences (Sprint 3; local) |
| `data/corrections/corrections.json` | Manual correction overlay (does not rewrite raw text) |
| `data/expected/structure_expectations.json` | Expected Parts/Schedules/article-count band |
| `data/rejected/unclassified_text.json` | Content that could not be confidently classified |

## Tests

```bash
pip install -e .
pytest -m "not integration"
```

Integration test (requires Docling + PDF):

```bash
pytest -m integration
```

- Pipeline fixtures: `tests/fixtures/`
- Learning fixtures: `tests/fixtures/learning/`
- Learning tests: `tests/test_learning_unit_generator.py`
- Progress / scheduler tests: `tests/test_reminder_engine.py`
- Web UI tests: `tests/test_web_app.py`, `tests/test_web_sprint5.py`

Unit tests **do not** require running Docling on the full PDF.

## Inspecting unclassified content

1. Open `data/rejected/unclassified_text.json`
2. Cross-check `data/output/constitution.json` → `unclassified_content`
3. Review `data/intermediate/parsing_events.json` for `unclassified_content` and `parser_transition` events

Unclassified blocks are retained so the corpus can be hardened in a later review phase.

## Configuration

Optional JSON config (see `--config`):

```json
{
  "known_headers": ["THE CONSTITUTION OF INDIA"],
  "minimum_header_page_frequency": 0.6,
  "near_duplicate_threshold": 0.96,
  "preserve_raw_text": true,
  "include_bounding_boxes": true
}
```

Defaults live in `src/constitution_memorizer/config.py`. Prefer extending config and `parsing/patterns.py` over hardcoding publisher-specific strings deep inside parsers.

## Adding rules for a different Bare Act edition

1. Run the pipeline and inspect `extraction_report.json` and `unclassified_text.json`
2. Add publisher-specific headers/footers to config `known_headers` / `known_footer_patterns`
3. Extend regexes in `src/constitution_memorizer/parsing/patterns.py` when structure differs
4. Add regression fixtures under `tests/fixtures/` for the new edge cases
5. Keep corrections as a **separate** override layer — do not silently rewrite raw extraction

## Known limitations

- Parser heuristics are deterministic but not perfect across every publisher layout
- Diglot / pocket editions with CONTENTS tables, schedule entry lists and appendix territorial “PART I/II/III” blocks can still create duplicate Article numbers; review `extraction_report.json`
- Chapters and omitted Articles depend on heading punctuation variants (including Docling’s `⎯` bar)
- Table structure depends on what Docling extracts; plain-text tables are preserved as body text when structural tables are absent
- Footnote ↔ Article association is best-effort
- Page/bounding-box provenance is only as rich as Docling metadata allows
- Real-PDF verification quality depends on the edition supplied in `data/input/`
- Some Articles (e.g. Art. 19 in the diglot pocket edition) have truncated flat bodies in extraction; the text fallback splitter only sees what is present in reviewed JSON
- The JSON is a **content foundation** for learning, not a certified legal database

## Real-PDF verification (this repository)

The pipeline has been run against `data/input/constitution_bare_act.pdf` (Legislative Department diglot pocket edition, Docling reported **402 pages**). Outputs are written under `data/` locally (most gitignored). Expect `completed_with_warnings` or `failed` status when duplicate Article IDs remain — that is intentional honesty, not a silent success. Phase 2 corpus review hardens publisher-specific rules. Learning units are regenerated with `generate-units` after corrections.

## Project layout

```text
src/constitution_memorizer/
  extraction/       # Docling PDF extraction
  normalization/    # Conservative text repair + repetition detection
  parsing/          # Constitution state machine and domain parsers
  validation/       # Structural checks and reports
  learning/         # Learning Units generator (Sprints 1–2+)
  progress/         # SQLite progress + ReminderEngine (Sprint 3+)
  web/              # FastAPI learning UI (Sprint 4+)
    templates/
    static/
  schemas.py        # Bare Act Pydantic models
  cli.py            # CLI entry
tests/              # Pytest suite and fixtures
  fixtures/learning/
data/               # Input PDF and generated artefacts
  progress/         # Local progress.db (gitignored)
```

## Documentation discipline

At the end of every sprint:

1. Update the sprint status table and that sprint’s section in this README
2. Document new CLI commands, output files, and test entry points
3. Keep “planned” sections short until the sprint starts

## Licence / disclaimer

This software assists study and research. It is **not** legal advice. Always verify against an official Bare Act publication.
