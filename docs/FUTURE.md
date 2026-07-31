# Future scope

Living backlog for **Recall the C**. Add items when discussed in chat/PRs; move them out when shipped (note the sprint/PR).

**Not** a substitute for Bare Act authority — study aid only.

---

## Shipped recently

| Item | Notes |
|------|--------|
| Footer + Home Reference & tools | Tables / Relevant laws / Memory log + theme in footer |
| Memory log | Separate `/memory` calendar (1→3→7→14→30), full-page detail with photo + notes |
| Relevant laws (Browse) | Seven Acts seed; list + detail; article chips |
| Native macOS reminders | `--channel macos`; digest includes Constitution + Memory dues |
| Browse due chrome (1c) | Corner ribbon, count line, In news pills, red nav badge |

Design handoff: [`docs/design/FOOTER-LAWS-MEMORY-HANDOFF.md`](design/FOOTER-LAWS-MEMORY-HANDOFF.md).

---

## Corpus / Bare Act text

| Item | Notes |
|------|--------|
| Clause / article cross-links in Learn | e.g. turn `clause (4)` into a link to that clause’s Learn unit |
| Broader diglot footnote → hover map | Beyond one-off annotations like Art 124(1) “seven”; systematic starred/numbered footers |
| More Judicial Evolution articles | Browse-only seed in `data/reference/judicial_evolution.seed.json` (Art 326 shipped; Learn stays modes-only) |
| Schedule & appendix text-pass | Same card-by-card corrections workflow as Articles |
| Struck-down amendments as Browse context | Show struck-down history without putting invalid wording in memorised body (body omit rule is **current** — see README / corrections notes) |

---

## Learning UI

| Item | Notes |
|------|--------|
| Law clauses as Learn units | Register each clause; six methods + Done; crumb `Relevant laws · {Act} ({year})`; enable Practice all |
| Soft Done when methods incomplete | Today Done is locked until all six methods are visited |
| Per-method mastery analytics | Beyond visit tracking |
| Offline / PWA shell | Local-first without always running `serve` |
| Richer Recite voice fallback | Improve unsupported-browser / network paths |
| Same-day-only Done + 6/day cap | Planned: block early Done; shared daily learning limit |

---

## Packaging / product

| Item | Notes |
|------|--------|
| Sprint 28 — Recall the C `.dmg` | Mac app packaging (see README changelog) |
| Multi-user / sync | Progress currently local SQLite only |
| Cloud photo sync for Memory log | Photos stay under `data/progress/memory_media/` locally |
| Official Bare Act edition switch | Alternate PDF editions via config/corrections without forking the app |

---

## How to update this file

1. New idea from review → add a row under the right section (one line).  
2. When implemented → delete the row (or move to a short “Shipped” note with PR number).  
3. Keep entries concrete; no speculative timelines.
