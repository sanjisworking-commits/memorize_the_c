"""Arts 31 (omit), 31A/33/34 restore, 244 vs 244A split."""

from __future__ import annotations

from constitution_memorizer.corrections.apply_corrections import (
    ArticleCorrection,
    CorrectionsFile,
    apply_corrections,
    load_corrections,
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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORRECTIONS = ROOT / "data" / "corrections" / "corrections.json"

_BODY_31A = (
    "(1) Notwithstanding anything contained in article 13, no law providing for—\n"
    "(a) the acquisition by the State of any estate or of any rights therein or "
    "the extinguishment or modification of any such rights; or\n"
    "(b) the taking over of the management of any property by the State for a "
    "limited period either in the public interest or in order to secure the proper "
    "management of the property; or\n"
    "(c) the amalgamation of two or more corporations either in the public interest "
    "or in order to secure the proper management of any of the corporations; or\n"
    "(d) the extinguishment or modification of any rights of managing agents, "
    "secretaries and treasurers, managing directors, directors or managers of "
    "corporations, or of any voting rights of shareholders thereof; or\n"
    "(e) the extinguishment or modification of any rights accruing by virtue of any "
    "agreement, lease or licence for the purpose of searching for, or winning, any "
    "mineral or mineral oil, or the premature termination or cancellation of any "
    "such agreement, lease or licence,\n"
    "shall be deemed to be void on the ground that it is inconsistent with, or takes "
    "away or abridges any of the rights conferred by article 14 or article 19:\n"
    "Provided that where such law is a law made by the Legislature of a State, the "
    "provisions of this article shall not apply thereto unless such law, having been "
    "reserved for the consideration of the President, has received his assent:\n"
    "Provided further that where any law makes any provision for the acquisition by "
    "the State of any estate and where any land comprised therein is held by a person "
    "under his personal cultivation, it shall not be lawful for the State to acquire "
    "any portion of such land as is within the ceiling limit applicable to him under "
    "any law for the time being in force or any building or structure standing thereon "
    "or appurtenant thereto, unless the law relating to the acquisition of such land, "
    "building or structure, provides for payment of compensation at a rate which shall "
    "not be less than the market value thereof.\n"
    "(2) In this article,—\n"
    '(a) the expression "estate" shall, in relation to any local area, have the same '
    "meaning as that expression or its local equivalent has in the existing law "
    "relating to land tenures in force in that area and shall also include—\n"
    "(i) any jagir, inam or muafi or other similar grant and in the States of Tamil "
    "Nadu and Kerala, any janmam right;\n"
    "(ii) any land held under ryotwari settlement;\n"
    "(iii) any land held or let for purposes of agriculture or for purposes ancillary "
    "thereto, including waste land, forest land, land for pasture or sites of buildings "
    "and other structures occupied by cultivators of land, agricultural labourers and "
    "village artisans;\n"
    '(b) the expression "rights", in relation to an estate, shall include any rights '
    "vesting in a proprietor, sub-proprietor, under-proprietor, tenure-holder, raiyat, "
    "under-raiyat or other intermediary and any rights or privileges in respect of "
    "land revenue."
)

_BODY_33 = (
    "Parliament may, by law, determine to what extent any of the rights conferred by "
    "this Part shall, in their application to,—\n"
    "(a) the members of the Armed Forces; or\n"
    "(b) the members of the Forces charged with the maintenance of public order; or\n"
    "(c) persons employed in any bureau or other organisation established by the State "
    "for purposes of intelligence or counter intelligence; or\n"
    "(d) person employed in, or in connection with, the telecommunication systems set "
    "up for the purposes of any Force, bureau or organisation referred to in clauses "
    "(a) to (c),\n"
    "be restricted or abrogated so as to ensure the proper discharge of their duties "
    "and the maintenance of discipline among them."
)

_BODY_34 = (
    "Notwithstanding anything in the foregoing provisions of this Part, Parliament "
    "may by law indemnify any person in the service of the Union or of a State or any "
    "other person in respect of any act done by him in connection with the maintenance "
    "or restoration of order in any area within the territory of India where martial "
    "law was in force or validate any sentence passed, punishment inflicted, forfeiture "
    "ordered or other act done under martial law in such area."
)

_BODY_244 = (
    "(1) The provisions of the Fifth Schedule shall apply to the administration and "
    "control of the Scheduled Areas and Scheduled Tribes in any State other than the "
    "States of Assam, Meghalaya, Tripura and Mizoram.\n"
    "(2) The provisions of the Sixth Schedule shall apply to the administration of the "
    "tribal areas in the States of Assam, Meghalaya, Tripura and Mizoram."
)

_BODY_244A = (
    "(1) Notwithstanding anything in this Constitution, Parliament may, by law, form "
    "within the State of Assam an autonomous State comprising (whether wholly or in "
    "part) all or any of the tribal areas specified in Part I of the table appended to "
    "paragraph 20 of the Sixth Schedule and create therefor—\n"
    "(a) a body, whether elected or partly nominated and partly elected, to function "
    "as a Legislature for the autonomous State, or\n"
    "(b) a Council of Ministers,\n"
    "or both with such constitution, powers and functions, in each case, as may be "
    "specified in the law.\n"
    "(2) Any such law as is referred to in clause (1) may, in particular,—\n"
    "(a) specify the matters enumerated in the State List or the Concurrent List with "
    "respect to which the Legislature of the autonomous State shall have power to make "
    "laws for the whole or any part thereof, whether to the exclusion of the Legislature "
    "of the State of Assam or otherwise;\n"
    "(b) define the matters with respect to which the executive power of the autonomous "
    "State shall extend;\n"
    "(c) provide that any tax levied by the State of Assam shall be assigned to the "
    "autonomous State in so far as the proceeds thereof are attributable to the "
    "autonomous State;\n"
    "(d) provide that any reference to a State in any article of this Constitution "
    "shall be construed as including a reference to the autonomous State; and\n"
    "(e) make such supplemental, incidental and consequential provisions as may be "
    "deemed necessary.\n"
    "(3) An amendment of any such law as aforesaid in so far as such amendment relates "
    "to any of the matters specified in sub-clause (a) or sub-clause (b) of clause (2) "
    "shall have no effect unless the amendment is passed in each House of Parliament by "
    "not less than two-thirds of the members present and voting.\n"
    "(4) Any such law as is referred to in this article shall not be deemed to be an "
    "amendment of this Constitution for the purposes of article 368 notwithstanding that "
    "it contains any provision which amends or has the effect of amending this "
    "Constitution."
)


def _broken_doc() -> ConstitutionDocument:
    return ConstitutionDocument(
        document=DocumentMetadata(title="t", schema_version="1.0.0"),
        parts=[
            Part(
                id="part-iii",
                part_number="III",
                title="FUNDAMENTAL RIGHTS",
                articles=[
                    Article(
                        id="article-31",
                        article_number="31",
                        numeric_component=31,
                        title="Compulsory acquisition of property",
                        part_number="III",
                        status=ArticleStatus.ACTIVE,
                        body_text="3 [Saving of Certain Laws]",
                    ),
                    Article(
                        id="article-31a",
                        article_number="31A",
                        numeric_component=31,
                        suffix="A",
                        title="Saving of laws providing for acquisition of estates, etc",
                        part_number="III",
                        status=ArticleStatus.ACTIVE,
                        body_text="(b) the taking over of the management…",
                    ),
                    Article(
                        id="article-33",
                        article_number="33",
                        numeric_component=33,
                        title=(
                            "Power of Parliament to modify the rights conferred by "
                            "this Part in their application to Forces, etc"
                        ),
                        part_number="III",
                        status=ArticleStatus.ACTIVE,
                        body_text="(a) the members of the Armed Forces; or",
                    ),
                    Article(
                        id="article-34",
                        article_number="34",
                        numeric_component=34,
                        title=(
                            "Restriction on rights conferred by this Part while "
                            "martial law is in"
                        ),
                        part_number="III",
                        status=ArticleStatus.ACTIVE,
                        body_text="force in any area .-Notwithstanding…",
                    ),
                ],
            ),
            Part(
                id="part-x",
                part_number="X",
                title="THE SCHEDULED AND TRIBAL AREAS",
                articles=[
                    Article(
                        id="article-244",
                        article_number="244",
                        numeric_component=244,
                        title="Administration of Scheduled Areas and Tribal Areas",
                        part_number="X",
                        status=ArticleStatus.ACTIVE,
                        body_text=(
                            "(1) Fifth Schedule… (2) Sixth Schedule… "
                            "244A. Formation of an autonomous State…"
                        ),
                    ),
                ],
            ),
        ],
        extraction_summary=ExtractionSummary(),
    )


def _corrections() -> CorrectionsFile:
    return CorrectionsFile(
        articles={
            "article-31": ArticleCorrection(
                exclude=True,
                manual_review_status="excluded_omitted_article",
            ),
            "article-31a": ArticleCorrection(
                title="Saving of laws providing for acquisition of estates, etc",
                part_number="III",
                opening_text="",
                body_text=_BODY_31A,
                prefer_article_unit=True,
            ),
            "article-33": ArticleCorrection(
                title=(
                    "Power of Parliament to modify the rights conferred by this Part "
                    "in their application to Forces, etc"
                ),
                part_number="III",
                opening_text="",
                body_text=_BODY_33,
                prefer_article_unit=True,
            ),
            "article-34": ArticleCorrection(
                title=(
                    "Restriction on rights conferred by this Part while martial law "
                    "is in force in any area"
                ),
                part_number="III",
                opening_text="",
                body_text=_BODY_34,
            ),
            "article-244": ArticleCorrection(
                title="Administration of Scheduled Areas and Tribal Areas",
                part_number="X",
                opening_text="",
                body_text=_BODY_244,
            ),
            "article-244a": ArticleCorrection(
                create=True,
                title=(
                    "Formation of an autonomous State comprising certain tribal areas "
                    "in Assam and creation of local Legislature or Council of Ministers "
                    "or both therefor"
                ),
                part_number="X",
                opening_text="",
                body_text=_BODY_244A,
            ),
        }
    )


def test_article_31_excluded_and_neighbours_restored():
    reviewed, changes = apply_corrections(_broken_doc(), _corrections())
    nums = [a.article_number for p in reviewed.parts for a in p.articles]
    assert "31" not in nums
    assert any("excluded" in c for c in changes)

    by_num = {a.article_number: a for p in reviewed.parts for a in p.articles}
    assert by_num["31A"].body_text.startswith("(1) Notwithstanding")
    assert "(e) the extinguishment" in by_num["31A"].body_text
    assert "(2) In this article" in by_num["31A"].body_text
    assert "janmam right" in by_num["31A"].body_text
    assert by_num["31A"].prefer_article_unit is True

    assert by_num["33"].body_text.startswith("Parliament may, by law")
    assert by_num["33"].prefer_article_unit is True

    assert by_num["34"].title.endswith("force in any area")
    assert by_num["34"].body_text.startswith("Notwithstanding anything")
    assert not by_num["34"].body_text.startswith("force in any area")

    assert "244A" not in by_num["244"].body_text
    assert by_num["244"].body_text.startswith("(1) The provisions of the Fifth")
    assert "244A" in by_num
    assert "(4) Any such law" in by_num["244A"].body_text

    units = {u.id: u for u in generate_learning_units(reviewed).units}
    assert "article-31" not in units
    assert "article-31a" in units
    assert units["article-31a"].text.startswith("(1) Notwithstanding")
    assert "article-33" in units
    assert units["article-33"].text.startswith("Parliament may, by law")
    assert "article-34" in units
    assert units["article-34"].title.endswith("force in any area")
    assert "article-244-clause-1" in units
    assert "article-244-clause-2" in units
    assert "244A" not in units["article-244-clause-2"].text
    assert "article-244a-clause-1" in units
    assert "article-244a-clause-4" in units
    assert units["article-244a-clause-4"].text.startswith("(4)")


def test_corrections_json_includes_31_family_and_244_split():
    corr = load_corrections(CORRECTIONS)
    assert corr.articles["article-31"].exclude is True
    assert corr.articles["article-31a"].prefer_article_unit is True
    assert corr.articles["article-31a"].body_text.startswith("(1) Notwithstanding")
    assert "(2) In this article" in corr.articles["article-31a"].body_text
    assert corr.articles["article-33"].body_text.startswith("Parliament may, by law")
    assert corr.articles["article-34"].title.endswith("force in any area")
    assert "244A" not in (corr.articles["article-244"].body_text or "")
    assert corr.articles["article-244a"].create is True
    assert "(4)" in (corr.articles["article-244a"].body_text or "")
