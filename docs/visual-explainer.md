# Visual Explainers

Reusable Visual Explainer modal for Constitutional Articles that have a registered flowchart (or similar diagram).

## Adding a new Constitutional Visual Explainer

1. Add the approved SVG under [`src/constitution_memorizer/web/explainer_assets/`](../src/constitution_memorizer/web/explainer_assets/), with a `viewBox` on the root `<svg>` (required for fit/zoom). Keep letters in the filename when the Article number has them, e.g. `article-239AA.svg`.
2. Add **one** entry to `EXPLAINERS` in [`src/constitution_memorizer/web/explainers.py`](../src/constitution_memorizer/web/explainers.py):

```python
"239AA": {
    "file": "article-239AA.svg",
    "title": "Special provisions with respect to Delhi",
    "type": "flowchart",  # flowchart | mind map | decision tree | timeline | process
},
```

Optional overrides: `label` (CTA text), `band_title` / `band_lede` (Learn band copy).

3. Do **not** modify the Visual Explainer component, CSS, or JS for a new Article.
4. Browse and Learn read the registry automatically — Visualise appears only where an entry exists.
5. Change the shared modal/CSS/JS only when updating the **global** Visual Explainer design system.

## Auth and assets

- Diagrams are served only via auth-gated `GET /api/explainers/{article_id}` (not under public `/static/`).
- When multi-user mode is on, guests still see the Visualise CTA (discovery), but opening prompts the existing sign-in modal. After successful sign-in, the user returns to the same Browse/Learn URL and the pending Article intent resumes (resolved again against the server registry). Cancelling sign-in clears that pending intent.
- Single-user mode has no guest gate; the API serves freely.
