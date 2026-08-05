"""Browse-only text annotation surfaces filter for Learn vs Browse."""

from __future__ import annotations

import json
from pathlib import Path

from constitution_memorizer.web.text_annotations import (
    DEFAULT_SURFACES,
    TextAnnotation,
    annotations_for_article,
    annotations_for_unit,
    filter_annotations_for_surface,
    load_text_annotations,
)

ROOT = Path(__file__).resolve().parents[1]
ANNOTATIONS = ROOT / "data" / "reference" / "text_annotations.json"


def test_default_surfaces_are_browse_and_learn():
    ann = TextAnnotation(target="States", note="n")
    assert ann.surfaces == DEFAULT_SURFACES


def test_filter_annotations_for_surface_keeps_matching_only():
    both = TextAnnotation(target="a", note="both")
    browse_only = TextAnnotation(target="b", note="browse", surfaces=("browse",))
    learn_only = TextAnnotation(target="c", note="learn", surfaces=("learn",))
    anns = [both, browse_only, learn_only]
    assert [a.target for a in filter_annotations_for_surface(anns, "browse")] == ["a", "b"]
    assert [a.target for a in filter_annotations_for_surface(anns, "learn")] == ["a", "c"]


def test_load_parses_surfaces_browse_only(tmp_path: Path):
    path = tmp_path / "anns.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.2.0",
                "notes": {},
                "units": {
                    "article-323-clause-2": [
                        {
                            "target": "Governor",
                            "note": "diglot",
                            "surfaces": ["browse"],
                        }
                    ],
                    "article-54": [{"target": "States", "note": "includes NCT"}],
                },
            }
        )
    )
    catalog = load_text_annotations(path)
    assert catalog["article-323-clause-2"][0].surfaces == ("browse",)
    assert catalog["article-54"][0].surfaces == DEFAULT_SURFACES
    assert annotations_for_unit(catalog, "article-323-clause-2", surface="learn") == []
    assert annotations_for_unit(catalog, "article-323-clause-2", surface="browse")


def test_committed_diglot_tips_are_browse_only():
    catalog = load_text_annotations(ANNOTATIONS)
    browse_only_ids = (
        "article-320-clause-3",
        "article-323-clause-2",
        "article-329",
        "article-329a",
        "article-332-clause-1",
        "article-333",
    )
    for unit_id in browse_only_ids:
        anns = catalog.get(unit_id) or []
        assert anns, unit_id
        for ann in anns:
            assert ann.surfaces == ("browse",), unit_id
        assert annotations_for_unit(catalog, unit_id, surface="learn") == []
        assert annotations_for_unit(catalog, unit_id, surface="browse")

    # Art 330 population Explanation tip available on Learn.
    tip330 = annotations_for_unit(catalog, "article-330-clause-2", surface="learn")
    assert any(t.target == "population" for t in tip330)

    # Existing Learn tip still available.
    seven = annotations_for_unit(catalog, "article-124-clause-1", surface="learn")
    assert seven and seven[0].target == "seven"

    browse_323 = annotations_for_article(
        catalog, "323", ["article-323-clause-2"], surface="browse"
    )
    assert any(a.target == "Governor" for a in browse_323)
