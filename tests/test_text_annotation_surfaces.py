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
    assert "browse" in ann.surfaces
    assert "learn" in ann.surfaces


def test_filter_annotations_for_surface_keeps_matching_only():
    both = TextAnnotation(target="a", note="both")
    browse_only = TextAnnotation(
        target="b", note="browse", surfaces=("browse",)
    )
    learn_only = TextAnnotation(target="c", note="learn", surfaces=("learn",))
    anns = [both, browse_only, learn_only]

    browse = filter_annotations_for_surface(anns, "browse")
    assert [a.target for a in browse] == ["a", "b"]

    learn = filter_annotations_for_surface(anns, "learn")
    assert [a.target for a in learn] == ["a", "c"]


def test_load_parses_surfaces_browse_only(tmp_path: Path):
    path = tmp_path / "anns.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.2.0",
                "notes": {},
                "units": {
                    "article-123-clause-3": [
                        {
                            "target": "void",
                            "note": "cl. (4) omitted diglot footer",
                            "surfaces": ["browse"],
                        }
                    ],
                    "article-54": [
                        {
                            "target": "States",
                            "note": "includes NCT",
                        }
                    ],
                },
            }
        )
    )
    catalog = load_text_annotations(path)
    diglot = catalog["article-123-clause-3"][0]
    assert diglot.surfaces == ("browse",)
    defaulted = catalog["article-54"][0]
    assert defaulted.surfaces == DEFAULT_SURFACES

    learn_diglot = annotations_for_unit(
        catalog, "article-123-clause-3", surface="learn"
    )
    assert learn_diglot == []
    browse_diglot = annotations_for_unit(
        catalog, "article-123-clause-3", surface="browse"
    )
    assert len(browse_diglot) == 1
    assert browse_diglot[0].target == "void"


def test_committed_diglot_tips_are_browse_only():
    catalog = load_text_annotations(ANNOTATIONS)
    browse_only_ids = (
        "article-123-clause-3",
        "article-124b",
        "article-124c",
        "article-127-clause-1",
        "article-128",
        "article-132-clause-3",
        "article-144a",
        "article-151-clause-2",
        "article-153",
        "article-166-clause-3",
        "article-170-clause-3",
        "article-176-clause-1",
        "article-189-clause-3",
        "article-192-clause-1",
    )
    for unit_id in browse_only_ids:
        anns = catalog.get(unit_id) or []
        assert anns, unit_id
        for ann in anns:
            assert ann.surfaces == ("browse",), unit_id
        assert annotations_for_unit(catalog, unit_id, surface="learn") == []
        assert annotations_for_unit(catalog, unit_id, surface="browse")

    # Existing Learn tip still available on Learn.
    seven = annotations_for_unit(
        catalog, "article-124-clause-1", surface="learn"
    )
    assert seven and seven[0].target == "seven"

    browse_123 = annotations_for_article(
        catalog,
        "123",
        ["article-123-clause-3"],
        surface="browse",
    )
    assert any(a.target == "void" for a in browse_123)

    browse_192 = annotations_for_article(
        catalog,
        "192",
        ["article-192-clause-1", "article-192-clause-2"],
        surface="browse",
    )
    assert any(a.target == "Governor" for a in browse_192)
