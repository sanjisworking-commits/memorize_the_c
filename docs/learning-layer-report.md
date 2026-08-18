# Learning Layer Final Report (Sprints 1–5)

Generated from `data/output/learning_units.json` after Sprint 2 generation, with product surface completed in Sprint 5.

## 1. Generated learning units

**930** units

## 2. Distribution by type

| Type | Count |
|------|------:|
| PART_OVERVIEW | 19 |
| ARTICLE | 176 |
| CLAUSE | 479 |
| SUBCLAUSE | 225 |
| SCHEDULE_ENTRY | 31 |
| Split-capable clauses (`allows_letter_split`) | 123 |

## 3. Unit size (characters of unit text)

| Metric | Value |
|--------|------:|
| Average | 467.1 |
| Smallest | 3 (`article-329` — Article 329) |
| Largest | 22,309 (`schedule-third` — Schedule THIRD) |

## 4. Files created / modified (learning layer)

### Created

- `src/constitution_memorizer/learning/` — schemas, generator, time/difficulty, text fallback
- `src/constitution_memorizer/progress/` — SQLite DB, repository, ReminderEngine
- `src/constitution_memorizer/web/` — FastAPI app, templates, static CSS/JS, browse/search/progress helpers
- `data/output/learning_units.json` (+ `.min.json`)
- `data/progress/.gitkeep`
- `tests/fixtures/learning/`
- `tests/test_learning_unit_generator.py`
- `tests/test_reminder_engine.py`
- `tests/test_web_app.py`
- `tests/test_web_sprint5.py`
- `docs/learning-layer-report.md`

### Modified

- `src/constitution_memorizer/cli.py` — `generate-units`, `serve`
- `README.md` — phase/sprint documentation
- `pyproject.toml` / `requirements.txt` — FastAPI stack deps
- `.gitignore` — allow learning units; ignore progress DB

**Not modified:** `data/output/constitution.reviewed.json`, Docling outputs, parser, corrections modules.

## 5. SQLite schema

Path: `data/progress/progress.db` (local)

```sql
learning_unit_progress(
  learning_unit_id TEXT PRIMARY KEY,
  status TEXT NOT NULL,              -- new | review | mastered
  times_completed INTEGER NOT NULL,
  last_completed TEXT,
  next_revision TEXT,
  interval_days INTEGER NOT NULL,
  ease_factor REAL NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

split_preference(
  parent_clause_id TEXT PRIMARY KEY,
  mode TEXT NOT NULL CHECK (mode IN ('whole', 'letters')),
  updated_at TEXT NOT NULL
);
```

Interval ladder: `1 → 3 → 7 → 15 → 30 → 60` days, then `mastered`.

## 6. Example learning paths

### Whole-clause path (default)

When preference is unset or `whole` for split-capable clauses:

1. Part III overview  
2. Short articles (e.g. Article 14) as a single `ARTICLE` unit  
3. Numbered clauses as `CLAUSE` units (e.g. Article 20(1) → 20(2) → 20(3) as one card)  
4. Continue to Article 21, …

### Letter path (after Choose → “Split into letters”)

For a clause such as Article 25(2) with `(a)(b)`:

1. Choose **letters** on `article-25-clause-2`  
2. Learn `…-subclause-a` → `…-subclause-b`  
3. Resume the global chain at the next clause-level unit  

Search deep-link `25(2)(a)` sets `letters` preference automatically and opens that subclause.

### Search examples

| Query | Result |
|-------|--------|
| `20` | Browse Article 20 (full Bare Act text + Learn CTAs) |
| `20(2)` | Learn clause (or Choose if split-capable and unset) |
| `25(2)(a)` | Set letters preference → Learn subclause |

## Branches

| Sprint | Branch |
|--------|--------|
| 1 | `cursor/sprint-1-learning-unit-generator-1a75` |
| 2 | `cursor/sprint-2-alphabetic-fallback-1a75` |
| 3 | `cursor/sprint-3-sqlite-scheduler-1a75` |
| 4 | `cursor/sprint-4-learn-home-ui-1a75` |
| 5 | `cursor/sprint-5-browse-search-progress-1a75` |
