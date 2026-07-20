# Constitution Memorizer

Production-oriented tooling to help users **understand, revise and memorise the Constitution of India**.

Work proceeds in two layers:

1. **Corpus pipeline (Phase 1–2)** — deterministic PDF → structured JSON for the Bare Act
2. **Learning layer (Sprints 1–20)** — Learning Units, progress, reminders, and a web UI aligned to the design prototype

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
| Sprints 8–20 | design prototype (see plan) | Planned |

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
- `GET /calendar` stub (full month grid in Sprint 18)
- Search page restyled to the same sheet tokens (`btn-accent`)
- Tests: `tests/test_web_sprint7.py`

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
