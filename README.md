# Constitution Memorizer

Production-oriented tooling to help users **understand, revise and memorise the Constitution of India**.

This repository currently implements **Phase 1 only**: a deterministic **PDF → structured JSON** pipeline for the Constitution of India Bare Act.

## Current scope (Phase 1)

- Project foundation (Python package, CLI, configuration)
- PDF extraction with [Docling](https://github.com/docling-project/docling)
- Conservative text normalisation (artefact repair only)
- Constitution-specific parsing into schema-validated JSON
- Validation and extraction reports
- Pytest coverage for the parsing pipeline
- Documentation for running the parser

## Future scope (not implemented)

Later phases may add corpus review, a canonical content model, database storage, search, memorisation units, spaced repetition, learning modes, explanation layers, APIs, frontend, accounts, and admin review. **Do not treat the current JSON as a finished learning product or an authoritative legal database.**

## Why exact legal text is preserved

The Bare Act wording is authoritative. The pipeline:

1. Keeps Docling’s raw extraction separate from normalised lines and structured JSON
2. Never silently rewrites, paraphrases or “beautifies” legal text
3. Records normalisation and parsing decisions as audit events
4. Retains unclassified content instead of dropping it

Editorial metadata, simplified explanations and memorisation aids (future phases) must remain separate from Bare Act text.

## Requirements

- Python **3.10+** (developed against 3.12)
- Dependencies listed in `requirements.txt` / `pyproject.toml` (`docling`, `pydantic`, `pytest`, `rapidfuzz`)

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

## Place the Bare Act PDF

Copy or link your Bare Act PDF to:

```text
data/input/constitution_bare_act.pdf
```

A source PDF may already exist in this repository. Generated artefacts under `data/raw`, `data/intermediate`, `data/output` and `data/rejected` are gitignored.

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
| `data/rejected/unclassified_text.json` | Content that could not be confidently classified |

## Tests

```bash
pip install -e .
pytest
```

Integration test (requires Docling + PDF):

```bash
pytest -m integration
```

Unit tests use small fixtures under `tests/fixtures/` and **do not** require running Docling on the full PDF.

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
5. Keep corrections as a **separate** override layer in a future phase—do not silently rewrite raw extraction

## Known limitations

- Parser heuristics are deterministic but not perfect across every publisher layout
- Table structure depends on what Docling extracts; plain-text tables are preserved as body text when structural tables are absent
- Footnote ↔ Article association is best-effort
- Page/bounding-box provenance is only as rich as Docling metadata allows
- Real-PDF verification quality depends on the edition supplied in `data/input/`
- The JSON is a **content foundation** for later phases, not a certified legal database

## Project layout

```text
src/constitution_memorizer/
  extraction/       # Docling PDF extraction
  normalization/    # Conservative text repair + repetition detection
  parsing/          # Constitution state machine and domain parsers
  validation/       # Structural checks and reports
  schemas.py        # Pydantic models
  cli.py            # CLI entry
tests/              # Pytest suite and fixtures
data/               # Input PDF and generated artefacts
```

## Licence / disclaimer

This software assists study and research. It is **not** legal advice. Always verify against an official Bare Act publication.
