"""Article 31C operative Bare Act correction."""

from __future__ import annotations

from constitution_memorizer.corrections.apply_corrections import (
    ArticleCorrection,
    CorrectionsFile,
    apply_corrections,
)
from constitution_memorizer.learning.learning_unit_generator import generate_learning_units
from constitution_memorizer.schemas import (
    Article,
    ArticleStatus,
    ConstitutionDocument,
    DocumentMetadata,
    ExtractionSummary,
    Part,
)
from constitution_memorizer.web.browse import _article_full_text

_DESIRED = (
    "Notwithstanding anything contained in article 13, no law giving effect to the "
    "policy of the State towards securing the principles specified in clause (b) or "
    "clause (c) of article 39 shall be deemed to be void on the ground that it is "
    "inconsistent with, or takes away or abridges any of the rights conferred by "
    "article 14 or article 19:\n"
    "Provided that where such law is made by the Legislature of a State, the "
    "provisions of this article shall not apply thereto unless such law, having been "
    "reserved for the consideration of the President, has received his assent."
)


def test_article_31c_restored_to_operative_bare_act():
    doc = ConstitutionDocument(
        document=DocumentMetadata(title="t", schema_version="1.0.0"),
        parts=[
            Part(
                id="part-iii",
                part_number="III",
                title="FUNDAMENTAL RIGHTS",
                articles=[
                    Article(
                        id="article-31c",
                        article_number="31C",
                        numeric_component=31,
                        suffix="C",
                        title="Saving of laws giving effect to certain directive principles",
                        part_number="III",
                        status=ArticleStatus.ACTIVE,
                        body_text=(
                            "Notwithstanding anything contained in article 13, no law "
                            "giving effect to the policy of the State towards securing "
                            "4 [all or any of the principles laid down in Part IV] shall "
                            "be deemed to be void on the ground that it is inconsistent "
                            "with, or takes away or abridges any of the rights conferred "
                            "by 5 [article 14 or article 19;] 6 [ and no law containing a "
                            "declaration that it is for giving effect to such policy shall "
                            "be called in question in any court on the ground that it does "
                            "not give effect to such policy]: 7 31D . [ Saving of laws in "
                            "respect of anti-national activities. ]. -Omitted by the "
                            "Constitution ( Forty-third Amendment ) Act, 1977 , s . 2 "
                            "( w.e.f. 13-4-1978) .\n"
                            "Provided that where such law is made by the Legislature of a "
                            "State, the provisions of this article shall not apply thereto "
                            "unless such law, having been reserved for the consideration "
                            "of the President, has received his assent.]"
                        ),
                    )
                ],
            )
        ],
        extraction_summary=ExtractionSummary(),
    )
    reviewed, _ = apply_corrections(
        doc,
        CorrectionsFile(
            articles={
                "article-31c": ArticleCorrection(
                    opening_text="",
                    body_text=_DESIRED,
                )
            }
        ),
    )
    art = next(a for p in reviewed.parts for a in p.articles)
    full = _article_full_text(art)
    assert full == _DESIRED
    assert "Part IV" not in full
    assert "declaration that it is for giving effect" not in full
    assert "31D" not in full
    assert "clause (b) or clause (c) of article 39" in full
    assert "Provided that where such law is made by the Legislature" in full

    units = {u.id: u for u in generate_learning_units(reviewed).units}
    assert "article-31c" in units
    assert units["article-31c"].text == _DESIRED
