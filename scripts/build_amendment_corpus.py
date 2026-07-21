#!/usr/bin/env python3
"""Build amendments.wikipedia.json + amendments.seed.json from curated Wikipedia rows.

Source: https://en.wikipedia.org/wiki/List_of_amendments_of_the_Constitution_of_India
Retrieved: 2026-07-20 (agent fetch). Not a legal authority — Bare Act text remains authoritative.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEWED = ROOT / "data" / "output" / "constitution.reviewed.json"
OUT_WIKI = ROOT / "data" / "reference" / "amendments.wikipedia.json"
OUT_SEED = ROOT / "data" / "reference" / "amendments.seed.json"
EXISTING_SEED = OUT_SEED

# (no, amendments_cell, enforced, objectives)
# Hand-transcribed from Wikipedia list (1st–106th).
WIKI_ROWS: list[tuple[str, str, str, str]] = [
    ("1st", "15, 19, 85, 87, 174, 176, 341, 342, 372 and 376. Insert articles 31A and 31B. Insert schedule 9.", "1951", "Special provisions for backward classes; zamindari abolition validity; reasonable restrictions on speech; Ninth Schedule device."),
    ("2nd", "Amend article 81(1)(b).", "1953", "Removed upper population limit for parliamentary constituencies under Article 81(1)(b)."),
    ("3rd", "Amend schedule 7.", "1955", "Re-enacted Concurrent List entry 33 on essential commodities trade and production."),
    ("4th", "Amend articles 31, 31A, and 305. Amend schedule 9.", "1955", "Property rights and state acquisition; agricultural land ceilings; mineral and oil control."),
    ("5th", "Amend article 3.", "1955", "President may prescribe/extend time for State Legislatures to respond on State formation bills."),
    ("6th", "Amend articles 269 and 286. Amend schedule 7.", "1956", "Union and State List tax-raising adjustments."),
    ("7th", "Amend articles 1, 3, 49, 80, 81, 82, 131, 153, 158, 168, 170, 171, 216, 217, 220, 222, 224, 230, 231 and 232. Insert articles 258A, 290A, 298, 350A, 350B, 371, 372A and 378A. Amend part 8. Amend schedules 1, 2, 4 and 7.", "1956", "States reorganisation on linguistic lines; Class A–D states abolished; Union territories introduced."),
    ("8th", "Amend article 334.", "1960", "Extended SC/ST and Anglo-Indian seat reservations in Lok Sabha and Assemblies till 1970."),
    ("9th", "Amend schedule 1.", "1960", "Territory adjustments with Pakistan after border village demarcation."),
    ("10th", "Amend article 240. Amend schedule 1.", "1961", "Dadra and Nagar Haveli incorporated as a Union Territory."),
    ("11th", "Amend articles 66 and 71.", "1961", "Vice-President elected by both Houses; election procedure insulated from electoral-college vacancies."),
    ("12th", "Amend article 240. Amend schedule 1.", "1961", "Goa, Daman and Diu incorporated as a Union Territory."),
    ("13th", "Amend article 170. Insert new article 371A.", "1962", "Special protection under Article 371A for Nagaland."),
    ("14th", "Amend articles 81 and 240. Insert article 239A. Amend schedules 1 and 4.", "1962", "Pondicherry incorporated; assemblies for certain Union Territories."),
    ("15th", "Amend articles 124, 128, 217, 222, 224, 226, 297, 311 and 316. Insert article 224A. Amend schedule 7.", "1963", "High Court judge retirement age raised to 62; related judicial rationalisations."),
    ("16th", "Amend articles 19, 84 and 173. Amend schedule 3.", "1963", "Public-office oaths of allegiance; sovereignty/integrity restrictions on speech."),
    ("17th", "Amend article 31A. Amend schedule 9.", "1964", "Secured acquisition of estates; more land laws under Ninth Schedule."),
    ("18th", "Amend article 3.", "1966", "Union Territories included in Article 3 reorganisation power."),
    ("19th", "Amend article 324.", "1966", "Election Tribunals abolished; election petitions to High Courts."),
    ("20th", "Insert article 233A.", "1966", "Validated certain judicial appointments and judgments after Article 233 litigation."),
    ("21st", "Amend schedule 8.", "1967", "Sindhi added as an official language."),
    ("22nd", "Amend article 275. Insert articles 244A and 371B.", "1969", "Autonomous states within Assam; related finance provisions."),
    ("23rd", "Amend articles 330, 332, 333 and 334.", "1970", "SC/ST/Anglo-Indian reservations extended; Nagaland ST reservation discontinued."),
    ("24th", "Amend articles 13 and 368.", "1971", "Parliament empowered to amend Fundamental Rights; presidential assent to amendment bills made obligatory."),
    ("25th", "Amend article 31. Insert article 31C.", "1971", "Restricted property rights and compensation; inserted Article 31C (part later limited by courts)."),
    ("26th", "Amend article 366. Insert article 363A. Remove articles 291 and 362.", "1971", "Abolished privy purses of former princely rulers."),
    ("27th", "Amend articles 239A and 240. Insert articles 239B and 371C.", "1972", "Mizoram UT with legislature; Manipur special provision 371C."),
    ("28th", "Insert article 312A. Remove article 314.", "1972", "Rationalised civil-service rules across pre- and post-Independence appointees."),
    ("29th", "Amend schedule 9.", "1972", "Kerala land-reform acts placed under Ninth Schedule."),
    ("30th", "Amend article 133.", "1972", "Supreme Court civil appeals based on substantial question of law, not value."),
    ("31st", "Amend articles 81, 330 and 332.", "1973", "Parliament size increased; North-East seat adjustments."),
    ("32nd", "Amend article 371. Insert articles 371D and 371E. Amend schedule 7.", "1974", "Regional protections for Telangana and Andhra; related entries."),
    ("33rd", "Amend articles 101 and 190.", "1974", "Resignation procedure for MPs and MLAs."),
    ("34th", "Amend schedule 9.", "1974", "Further land-reform acts under Ninth Schedule."),
    ("35th", "Amend articles 80 and 81. Insert article 2A. Insert schedule 10.", "1975", "Terms for incorporating Sikkim into the Union."),
    ("36th", "Amend articles 80 and 81. Insert article 371F. Remove article 2A. Amend schedules 1 and 4. Remove schedule 10.", "1975", "Sikkim became a State; Article 371F special provisions."),
    ("37th", "Amend articles 239A and 240.", "1975", "Arunachal Pradesh legislative assembly."),
    ("38th", "Amend articles 123, 213, 239B, 352, 356, 359 and 360.", "1975", "Expanded ordinance and emergency powers of President and Governors."),
    ("39th", "Amend articles 71 and 329. Insert article 329A. Amend schedule 9.", "1975", "Restricted judicial scrutiny of certain high offices’ elections (parts later struck down)."),
    ("40th", "Amend article 297. Amend schedule 9.", "1976", "EEZ mineral wealth vested in the Union; more Ninth Schedule acts."),
    ("41st", "Amend article 316.", "1976", "Raised retirement age for State/Joint PSC members to 62."),
    ("42nd", "Amend articles 31, 31C, 39, 55, 74, 77, 81, 82, 83, 100, 102, 103, 105, 118, 145, 150, 166, 170, 172, 189, 191, 192, 194, 208, 217, 225, 226, 227, 228, 311, 312, 330, 352, 353, 356, 357, 358, 359, 366, 368 and 371F. Insert articles 31D, 32A, 39A, 43A, 48A, 131A, 139A, 144A, 226A, 228A and 257A. Insert parts IVA and XIVA. Amend schedule 7.", "1977", "Emergency-era overhaul: socialist/secular wording, duties, many institutional changes (parts later curtailed)."),
    ("43rd", "Amend articles 145, 226, 228 and 366. Remove articles 31D, 32A, 131A, 144A, 226A and 228A.", "1978", "Repealed several 42nd Amendment anti-freedom inserts."),
    ("44th", "Amend articles 19, 22, 30, 31A, 31C, 38, 71, 74, 77, 83, 103, 105, 123, 132, 133, 134, 139A, 150, 166, 172, 192, 194, 213, 217, 225, 226, 227, 239B, 329, 352, 356, 358, 359, 360 and 371F. Insert articles 134A and 361A. Remove articles 31, 257A and 329A. Amend part 12. Amend schedule 9.", "1979", "Restored liberties after Emergency; omitted property as a fundamental right (Art 19(1)(f) / Art 31)."),
    ("45th", "Amend article 334.", "1980", "Extended SC/ST and Anglo-Indian reservations till 1990."),
    ("46th", "Amend articles 269, 286 and 366. Amend schedule 7.", "1983", "Sales-tax scope clarifications after judicial rulings."),
    ("47th", "Amend schedule 9.", "1984", "Further land-reform acts under Ninth Schedule."),
    ("48th", "Amend article 356.", "1984", "President's rule up to two years permitted in Punjab."),
    ("49th", "Amend article 244. Amend schedules 5 and 6.", "1984", "Tripura tribal areas autonomous district council enabled."),
    ("50th", "Amend article 33.", "1984", "Expanded Article 33 curtailment of Part III rights for certain security personnel."),
    ("51st", "Amend articles 330 and 332.", "1984", "ST reservations in certain North-East Lok Sabha/Assembly seats."),
    ("52nd", "Amend articles 101, 102, 190 and 191. Insert schedule 10.", "1985", "Anti-defection law (Tenth Schedule)."),
    ("53rd", "Insert article 371G.", "1986", "Special provision for Mizoram."),
    ("54th", "Amend articles 125 and 221. Amend schedule 2.", "1986", "Judge salaries; future increases without constitutional amendment."),
    ("55th", "Insert article 371H.", "1987", "Special Governor powers for Arunachal Pradesh."),
    ("56th", "Insert article 371I.", "1987", "Transition provision for Goa statehood."),
    ("57th", "Amend article 332.", "1987", "ST reservation in certain North-East Assemblies."),
    ("58th", "Insert article 394A. Amend part 22.", "1987", "Authentic Hindi text of the Constitution and future amendments."),
    ("59th", "Amend article 356. Insert article 359A.", "1988", "Extended President's rule/emergency tools for Punjab (later partly repealed)."),
    ("60th", "Amend article 276.", "1988", "Profession tax ceiling raised to ₹2,500."),
    ("61st", "Amend article 326.", "1989", "Voting age reduced from 21 to 18."),
    ("62nd", "Amend article 334.", "1990", "Extended SC/ST and Anglo-Indian reservations till 2000."),
    ("63rd", "Amend article 356. Remove article 359A.", "1990", "Repealed Punjab-specific Article 359A emergency power."),
    ("64th", "Amend article 356.", "1990", "President's rule in Punjab extendable to three years six months."),
    ("65th", "Amend article 338.", "1992", "National Commission for SCs and STs given constitutional status/powers."),
    ("66th", "Amend schedule 9.", "1990", "Further land-reform acts under Ninth Schedule."),
    ("67th", "Amend article 356.", "1990", "President's rule in Punjab extendable to four years."),
    ("68th", "Amend article 356.", "1991", "President's rule in Punjab extendable to five years."),
    ("69th", "Insert articles 239AA and 239AB.", "1992", "Legislative assembly and council of ministers for NCT of Delhi."),
    ("70th", "Amend articles 54 and 239AA.", "1991", "Delhi and Pondicherry included in presidential electoral college."),
    ("71st", "Amend schedule 8.", "1992", "Konkani, Manipuri and Nepali added as official languages."),
    ("72nd", "Amend article 332.", "1992", "ST reservation in Tripura Assembly."),
    ("73rd", "Insert part 9. Insert schedule 11.", "1993", "Constitutional status for Panchayati Raj (Part IX)."),
    ("74th", "Insert part 9A, insert schedule 12, amend article 280.", "1993", "Constitutional status for municipalities (Part IXA); Finance Commission tweaks."),
    ("75th", "Amend article 323B.", "1994", "Enabled Rent Control Tribunals."),
    ("76th", "Amend schedule 9.", "1994", "Tamil Nadu reservation Act protected via Ninth Schedule."),
    ("77th", "Amend article 16.", "1995", "Protected reservation in promotions for SCs/STs."),
    ("78th", "Amend schedule 9.", "1995", "Further land-reform acts under Ninth Schedule."),
    ("79th", "Amend article 334.", "2000", "Extended SC/ST and Anglo-Indian reservations till 2010."),
    ("80th", "Amend articles 269 and 270. Remove article 272.", "2000", "Tax pooling/sharing per Tenth Finance Commission; Article 272 omitted."),
    ("81st", "Amend article 16.", "2000", "Protected filling SC/ST reservation backlog vacancies."),
    ("82nd", "Amend article 335.", "2000", "Allowed relaxed standards in SC/ST promotion reservations."),
    ("83rd", "Amend article 243M.", "2000", "Exempted Arunachal Pradesh from SC reservation in Panchayats."),
    ("84th", "Amend articles 55, 81, 82, 170, 330 and 332.", "2002", "Froze seat distribution on 1971 census figures."),
    ("85th", "Amend article 16.", "2002", "Protected consequential seniority for SC/ST promotees."),
    ("86th", "Amend articles 45 and 51A. Insert article 21A.", "2002", "Right to education for children 6–14; related DPSP and duty changes."),
    ("87th", "Amend articles 81, 82, 170 and 330.", "2003", "Seat distribution updated using 2001 census figures."),
    ("88th", "Amend article 270. Insert article 268A. Amend schedule 7.", "2004", "Service tax statutory cover (Article 268A later removed by GST)."),
    ("89th", "Amend article 338. Insert article 338A.", "2003", "Split SC and ST national commissions."),
    ("90th", "Amend article 332.", "2003", "Assam Assembly reservation for Bodoland areas."),
    ("91st", "Amend articles 75 and 164. Insert article 361B. Amend schedule 10.", "2004", "Council of Ministers size capped; anti-defection strengthened."),
    ("92nd", "Amend schedule 8.", "2004", "Bodo, Dogri, Santali and Maithili added as official languages."),
    ("93rd", "Amend article 15.", "2006", "Enabled OBC reservation in educational institutions including private unaided."),
    ("94th", "Amend article 164.", "2006", "Tribal Welfare Minister for Jharkhand, Chhattisgarh, Madhya Pradesh, Odisha."),
    ("95th", "Amend article 334.", "2010", "Extended SC/ST and Anglo-Indian reservations till 2020."),
    ("96th", "Amend schedule 8.", "2011", "Oriya renamed Odia in the Eighth Schedule."),
    ("97th", "Amend Art 19 and add Art 43B and Part IXB.", "2012", "Co-operative societies in Art 19(1)(c); Art 43B and Part IXB (part later struck)."),
    ("98th", "Insert Article 371J.", "2013", "Special development provision for Hyderabad-Karnataka region."),
    ("99th", "Insert articles 124A, 124B and 124C. Amend articles 127, 128, 217, 222, 224A, 231.", "2015", "National Judicial Appointments Commission (struck down by Supreme Court)."),
    ("100th", "Amend First Schedule.", "2015", "India–Bangladesh land boundary enclave exchange."),
    ("101st", "Add articles 246A, 269A, 279A. Delete Article 268A. Amend articles 248, 249, 250, 268, 269, 270, 271, 286, 366, 368, Sixth Schedule, Seventh Schedule.", "2017", "Goods and Services Tax framework."),
    ("102nd", "Add articles 338B, 342A. Modify articles 338, 366.", "2018", "Constitutional status for National Commission for Backward Classes."),
    ("103rd", "Amend Article 15 and Article 16 (EWS clauses).", "2019", "Up to 10% reservation for Economically Weaker Sections."),
    ("104th", "Amend article 334.", "2020", "Extended SC/ST reservations till 2030; ended Anglo-Indian nominated seats."),
    ("105th", "Amend Article 338B, 342A and 366.", "2021", "Restored States’ power to identify SEBC/OBC lists."),
    ("106th", "Amend article 239AA. Insert articles 330A, 332A, 334A.", "2023", "One-third seats reserved for women in Lok Sabha, Assemblies and Delhi Assembly (timed)."),
]

# When Wikipedia only names a Part, map to in-corpus article ranges.
PART_ARTICLE_RANGES: dict[str, tuple[str, ...]] = {
    # Part IX — Panchayats (Art 243–243O)
    "part 9": tuple(
        ["243"]
        + [f"243{c}" for c in "ABCDEFGHIJKLMNO"]
    ),
    "part ix": tuple(
        ["243"]
        + [f"243{c}" for c in "ABCDEFGHIJKLMNO"]
    ),
    # Part IXA — Municipalities (Art 243P–243ZG)
    "part 9a": tuple([f"243{c}" for c in "PQRSTUVWXYZ"] + ["243ZA", "243ZB", "243ZC", "243ZD", "243ZE", "243ZF", "243ZG"]),
    "part ixa": tuple([f"243{c}" for c in "PQRSTUVWXYZ"] + ["243ZA", "243ZB", "243ZC", "243ZD", "243ZE", "243ZF", "243ZG"]),
    # Part IXB — Co-operative societies (Art 243ZH–243ZT) if present
    "part ixb": tuple(
        [f"243Z{c}" for c in "HIJKLMNOPQRST"]
    ),
    # Part IVA — Fundamental duties (Art 51A only in practice)
    "part iva": ("51A",),
    "part iv a": ("51A",),
}


def expand_part_refs(cell: str, corpus: set[str]) -> list[str]:
    low = (
        cell.lower()
        .replace("part-ixb", "part ixb")
        .replace("part-ixa", "part ixa")
        .replace("part-ix", "part ix")
        .replace("part-9a", "part 9a")
        .replace("part-9", "part 9")
    )
    out: list[str] = []
    # Longer / more specific keys first so "part 9a" wins over "part 9".
    ordered = sorted(PART_ARTICLE_RANGES.keys(), key=len, reverse=True)
    matched_spans: list[str] = []
    for key in ordered:
        # Skip if this key is only a prefix of an already-matched longer key.
        if any(key != m and key in m for m in matched_spans):
            continue
        if key in low:
            matched_spans.append(key)
            for a in PART_ARTICLE_RANGES[key]:
                if a in corpus and a not in out:
                    out.append(a)
    return out
ARTICLE_TOKEN_RE = re.compile(
    r"\b(?:articles?|art\.?)\s+([0-9A-Za-z,\s\-and]+?)(?=(?:\.|;|Insert|Remove|Amend|Add|Delete|Modification|and add|and Part|and Schedule|Schedule|Part|$))",
    re.I,
)
BARE_NUM_RE = re.compile(r"\b(\d{1,3}[A-Z]{0,2})\b")
SCHEDULE_ONLY_RE = re.compile(r"schedule|part\s+IX|part\s+9|first schedule|sixth schedule|seventh schedule|eighth schedule|ninth schedule|tenth schedule|eleventh schedule|twelfth schedule", re.I)


def corpus_article_ids() -> set[str]:
    doc = json.loads(REVIEWED.read_text(encoding="utf-8"))
    ids: set[str] = set()

    def walk(arts):
        for a in arts or []:
            n = a.get("article_number") or a.get("number")
            if n:
                ids.add(str(n))

    for p in doc.get("parts") or []:
        walk(p.get("articles"))
        for ch in p.get("chapters") or []:
            walk(ch.get("articles"))
    return ids


def parse_articles_touched(cell: str) -> list[str]:
    """Extract article numbers from the Wikipedia Amendments column."""
    found: list[str] = []
    seen: set[str] = set()

    def add(tok: str) -> None:
        tok = tok.strip().rstrip(".")
        if not tok or tok.lower() in {"and", "or"}:
            return
        if re.fullmatch(r"\d+[A-Za-z]+", tok):
            m = re.match(r"(\d+)([A-Za-z]+)", tok)
            assert m
            tok = m.group(1) + m.group(2).upper()
        if tok not in seen and re.fullmatch(r"\d{1,3}[A-Z]{0,2}", tok):
            # Filter absurd matches (years etc. already excluded by 1–3 digits)
            if int(re.match(r"\d+", tok).group(0)) > 400 and not re.search(r"[A-Z]", tok):
                return
            seen.add(tok)
            found.append(tok)

    # Strip parenthetical clause refs: 81(1)(b) -> 81
    cleaned = re.sub(r"\(\d+(?:\([a-z]\))?\)", "", cell, flags=re.I)
    cleaned = re.sub(r"\([a-z]\)", "", cleaned, flags=re.I)

    for m in re.finditer(
        r"(?i)(?:amend|insert|remove|add|delete|modification of)\s+"
        r"(?:new\s+)?(?:articles?|art\.?)?\s*:?\s*"
        r"([0-9A-Za-z,\s\[\]\-and]+?)"
        r"(?=(?:\.|;|Insert|Remove|Amend|Add|Delete|Modification|and add Part|and Part|"
        r"and Schedule|,?\s*Amend schedule|,?\s*Insert schedule|,?\s*Amend part|"
        r",?\s*Insert part|$))",
        cleaned,
    ):
        chunk = m.group(1)
        for piece in re.split(r",|\band\b", chunk):
            piece = piece.strip()
            piece = re.sub(r"^\[|\]$", "", piece).strip()
            if re.search(r"(?i)schedule|part|clause", piece):
                continue
            for tok in BARE_NUM_RE.findall(piece):
                add(tok)

    lead = cleaned.split("Insert", 1)[0].split("Amend schedule", 1)[0]
    if re.match(r"^\s*\d", lead):
        for tok in BARE_NUM_RE.findall(lead):
            add(tok)

    return found


def year_from_enforced(enforced: str) -> str:
    # Prefer last 4-digit year in the string
    years = re.findall(r"(19|20)\d{2}", enforced)
    if not years:
        # enforced may already be just a year in our table
        if re.fullmatch(r"(19|20)\d{2}", enforced.strip()):
            return enforced.strip()
        return enforced.strip()[:4]
    # re.findall with groups returns tuples - fix
    years = re.findall(r"((?:19|20)\d{2})", enforced)
    return years[-1]


def action_for(article: str, cell: str) -> str:
    low = cell.lower()
    patterns = [
        (rf"insert[^.]*\b{re.escape(article)}\b", "Inserted"),
        (rf"add[^.]*\b{re.escape(article)}\b", "Inserted"),
        (rf"remove[^.]*\b{re.escape(article)}\b", "Removed"),
        (rf"delete[^.]*\b{re.escape(article)}\b", "Removed"),
    ]
    for pat, label in patterns:
        if re.search(pat, cell, re.I):
            return label
    if re.search(rf"\b{re.escape(article)}\b", cell):
        return "Amended"
    # Part-level inserts (no per-article token in the cell)
    if re.search(r"insert\s+part", low):
        return "Inserted"
    return "Touched"


def card_text(article: str, no: str, year: str, cell: str, objectives: str) -> str:
    action = action_for(article, cell)
    # Short objective snippet (first sentence-ish, capped)
    obj = objectives.strip()
    if len(obj) > 160:
        cut = obj[:157].rsplit(" ", 1)[0] + "…"
    else:
        cut = obj
    if action == "Inserted":
        return f"Inserted by the {no} Amendment ({year}) — {cut}"
    if action == "Removed":
        return f"Omitted/removed by the {no} Amendment ({year}) — {cut}"
    return f"Amended by the {no} Amendment ({year}) — {cut}"


def learn_note_for(article: str, rows: list[dict]) -> str | None:
    """Editorial Learn footnote when the amendment story changes how text is read."""
    special = {
        "19": "The letters run (a)–(e), (g): sub-clause (f) — property — was omitted by the 44th Amendment (1978).",
        "21": "Unamended since 1950; the 86th Amendment (2002) added the companion Article 21A on education.",
        "15": "Amended thrice — clauses (4)–(6) were added by the 1st, 93rd and 103rd Amendments. See Amendment history under Browse.",
        "31": "Article 31 (property as a fundamental right) was omitted by the 44th Amendment (1978); related property rules moved elsewhere.",
        "368": "Amending power itself was reshaped by the 24th and 42nd Amendments (with later judicial limits on basic structure).",
        "356": "Repeatedly amended for President's Rule duration — especially Punjab-specific extensions in the 1980s–90s.",
        "16": "Promotion/reservation clauses (4A)/(4B)/(6) added by later amendments — read the current clauses carefully.",
        "334": "Reservation duration for SC/ST seats extended by successive amendments; Anglo-Indian nomination ended by the 104th (2020).",
        "21A": "Inserted by the 86th Amendment (2002) — free and compulsory education for children aged 6–14.",
        "31A": "Inserted by the 1st Amendment (1951) to protect certain property/estate laws.",
        "31B": "Inserted by the 1st Amendment (1951) with the Ninth Schedule validation device.",
        "31C": "Inserted by the 25th Amendment (1971); scope later narrowed by the Supreme Court.",
        "51A": "Fundamental duties — Part IVA inserted by the 42nd Amendment (1976); education duty tweaked by the 86th.",
        "326": "Voting age lowered from 21 to 18 by the 61st Amendment (1989).",
    }
    if article in special:
        return special[article]
    # Omitted articles
    if any(r["text"].startswith("Omitted") for r in rows):
        return f"See Amendment history — later amendments omitted or replaced parts of Article {article}."
    if len(rows) >= 4:
        return f"Amended {len(rows)} times — skim Amendment history under Browse before memorising the current wording."
    return None


def main() -> None:
    corpus = corpus_article_ids()
    existing = json.loads(EXISTING_SEED.read_text(encoding="utf-8")) if EXISTING_SEED.exists() else {"articles": {}}
    preserve = {k: existing["articles"][k] for k in ("14", "15", "19", "21") if k in existing.get("articles", {})}

    wiki_amendments = []
    by_article: dict[str, list[dict]] = defaultdict(list)

    for no, cell, enforced, objectives in WIKI_ROWS:
        year = year_from_enforced(enforced)
        touched = parse_articles_touched(cell)
        for extra in expand_part_refs(cell, corpus):
            if extra not in touched:
                touched.append(extra)
        wiki_amendments.append(
            {
                "no": no,
                "enforced": enforced if len(enforced) > 4 else year,
                "year": year,
                "articles_touched": touched,
                "amendments_cell": cell,
                "objectives": objectives,
            }
        )
        for art in touched:
            if art not in corpus:
                continue
            by_article[art].append(
                {
                    "no": no,
                    "year": year,
                    "text": card_text(art, no, year, cell, objectives),
                }
            )

    # Deduplicate identical (no, year) per article preserving order
    seed_articles: dict[str, dict] = {}
    for art, rows in sorted(by_article.items(), key=lambda kv: (len(kv[0]), kv[0])):
        uniq = []
        seen = set()
        for r in rows:
            key = (r["no"], r["year"], r["text"][:40])
            if key in seen:
                continue
            seen.add(key)
            uniq.append(r)
        seed_articles[art] = {
            "amendments": uniq,
            "learn_note": learn_note_for(art, uniq),
        }

    # Restore hand-curated 14/15/19/21
    for k, payload in preserve.items():
        seed_articles[k] = payload

    wiki_doc = {
        "schema_version": "1.0.0",
        "source": {
            "title": "List of amendments of the Constitution of India",
            "url": "https://en.wikipedia.org/wiki/List_of_amendments_of_the_Constitution_of_India",
            "retrieved": "2026-07-20",
            "note": "Reference extract for learning cards — not a substitute for the Bare Act or official amendment texts.",
        },
        "amendment_count": len(wiki_amendments),
        "amendments": wiki_amendments,
    }
    OUT_WIKI.write_text(json.dumps(wiki_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    seed_doc = {
        "schema_version": "1.0.0",
        "source": {
            "catalog": "data/reference/amendments.wikipedia.json",
            "url": "https://en.wikipedia.org/wiki/List_of_amendments_of_the_Constitution_of_India",
            "note": "Article timelines curated for Recall C Browse/Learn. Memorise current Bare Act wording.",
        },
        "articles": dict(sorted(seed_articles.items(), key=lambda kv: (len(kv[0]), kv[0]))),
    }
    OUT_SEED.write_text(json.dumps(seed_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    missing_from_corpus = sorted(
        {
            a
            for row in wiki_amendments
            for a in row["articles_touched"]
            if a not in corpus
        },
        key=lambda x: (len(x), x),
    )
    print(f"Wrote {OUT_WIKI} ({len(wiki_amendments)} amendments)")
    print(f"Wrote {OUT_SEED} ({len(seed_articles)} articles)")
    print(f"Skipped (not in corpus): {len(missing_from_corpus)} → {missing_from_corpus[:40]}…")
    for k in ("14", "15", "19", "21", "356", "368", "16"):
        print(k, "rows", len(seed_articles.get(k, {}).get("amendments", [])))


if __name__ == "__main__":
    main()
