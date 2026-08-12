"""Visual Explainer registry.

Article-specific data lives here and nowhere else. To add an Article: drop
'static/explainers/article-<n>.svg' in place and add one row to EXPLAINERS.

Keys are full constitutional identifiers, letters included: '82', '21A', '31C',
'239AA', '243G', '243ZG'. Clause references resolve to their parent Article, so
'Article 82(1)' and 'Article 21A(2)(b)' find '82' and '21A'.

Every SVG must carry a viewBox on its root tag. Lucid / draw.io exports often
ship width/height only, which makes the browser clip instead of scale, and the
viewer reads each diagram's intrinsic size from the file itself:

    <svg ... width="1415.61" height="3773.68" viewBox="0 0 1415.61 3773.68">

Wiring (one line in web/app.py, just after 'templates = Jinja2Templates(...)'):

    from .explainers import visual_explainer
    templates.env.globals["visual_explainer"] = visual_explainer
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

# Article identifier -> explainer metadata.
#   file       required — sits in static/explainers/
#   title      Article heading, shown in the modal subtitle
#   type       flowchart | mind map | decision tree | timeline | process
#   label      trigger label (default "Visualise")
#   band_title / band_lede  optional Learn-band copy overrides
EXPLAINERS: Dict[str, Dict[str, str]] = {
    "82": {
        "file": "article-82.svg",
        "title": "Readjustment after each census",
        "type": "flowchart",
        # "band_title": "Losing the order of events?",
        # "band_lede": "See the census → readjustment sequence as a flowchart.",
    },
    # "239AA": {"file": "article-239AA.svg", "title": "Special provisions for Delhi",
    #           "type": "decision tree"},
}

STATIC_PREFIX = "/static/explainers/"

# Default Learn-band copy. Generic on purpose: it reads correctly for a
# flowchart, a timeline or a mind map, for any Article.
BAND_TITLE = "Prefer to see it?"
BAND_LEDE = "Open the {type} for Article {article}{title_clause} — your place in this session is kept."

# "Article 82(1)" -> 82 · "Article 21A" -> 21A · "Article 243ZG(a)" -> 243ZG
_LABELLED = re.compile(r"[Aa]rt(?:icle)?\.?\s*(\d+)([A-Za-z]*)")
_BARE = re.compile(r"(\d+)([A-Za-z]*)")


def normalise_ref(article_ref: Any) -> Optional[str]:
    """Return the Article identifier named by *article_ref*, or None.

    Letters that belong to the Article number are kept and upper-cased ('21a'
    -> '21A', '239aa' -> '239AA'); a bracketed clause is not part of the
    identifier, so '82(1)' -> '82'. An 'Article NN' phrase wins over any other
    number in the string, so 'Clause (1) of Article 82' -> '82'.
    """
    if article_ref is None:
        return None
    text = str(article_ref)
    match = _LABELLED.search(text) or _BARE.search(text)
    if not match:
        return None
    return match.group(1) + match.group(2).upper()


def _entry(key: str) -> Optional[Dict[str, str]]:
    entry = EXPLAINERS.get(key)
    if entry is not None:
        return entry
    for raw, value in EXPLAINERS.items():   # tolerate '21a' / ' 21A ' in the registry
        if normalise_ref(raw) == key:
            return value
    return None


def visual_explainer(article_ref: Any) -> Optional[Dict[str, str]]:
    """Return explainer metadata for an Article, or None.

    Accepts anything that names an Article: 82, '82', '21A', 'Article 82(1)',
    or a learn unit's display_title. Pass unit.article_number when you have it.
    """
    key = normalise_ref(article_ref)
    if key is None:
        return None
    entry = _entry(key)
    if not entry:
        return None
    title = entry.get("title", "")
    kind = entry.get("type", "flowchart")
    return {
        "article": key,
        "src": STATIC_PREFIX + entry["file"],
        "title": title,
        "type": kind,
        "label": entry.get("label", "Visualise"),
        "band_title": entry.get("band_title", BAND_TITLE),
        "band_lede": entry.get(
            "band_lede",
            BAND_LEDE.format(
                type=kind,
                article=key,
                title_clause=(", " + title) if title else "",
            ),
        ),
    }


def has_visual_explainer(article_ref: Any) -> bool:
    return visual_explainer(article_ref) is not None
