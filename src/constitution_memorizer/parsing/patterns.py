"""Compiled regex patterns for Constitution Bare Act structure detection."""

from __future__ import annotations

import re

# Em dash, en dash, hyphen, and Docling's horizontal-bar (U+23AF).
_DASH = r"—\-–⎯−:"

# Constitution Parts only (I–XXII, including IVA / IXA / XIVA / XIVB).
# Schedule-internal "PART A/B/C…" headings are handled separately.
PART_RE = re.compile(
    r"^PART\s+"
    r"(?P<number>XXII|XXI|XX|XIX|XVIII|XVII|XVI|XV|XIVA|XIVB|XIV|XIII|XII|XI|X|"
    r"IXA|IX|VIII|VII|VI|V|IVA|IV|III|II|I)"
    rf"(?:\s*[{_DASH}]\s*(?P<title>.+))?$",
    re.IGNORECASE,
)

# Fifth/Sixth Schedule internal parts (PART A … PART E)
SCHEDULE_PART_RE = re.compile(
    r"^PART\s+(?P<letter>[A-E])"
    rf"(?:\s*[{_DASH}.]?\s*(?P<title>.+))?$",
    re.IGNORECASE,
)

CONTENTS_RE = re.compile(r"^CONTENTS\s*$", re.IGNORECASE)

PREFACE_RE = re.compile(r"^PREFACE\s*$", re.IGNORECASE)

LIST_OF_ABBREVIATIONS_RE = re.compile(
    r"^LIST OF ABBREVIATIONS(?:\s+USED)?\s*$",
    re.IGNORECASE,
)

# Reject absurd Article numbers (Bare Act tops out near 395).
MAX_ARTICLE_NUMBER = 450

PART_TITLE_ONLY_RE = re.compile(
    r"^(?P<title>THE\s+[A-Z][A-Z\s,'\-]+)$"
)

# CHAPTER I  /  CHAPTER II.—THE EXECUTIVE  /  CHAPTER I.-LANGUAGE
CHAPTER_RE = re.compile(
    r"^CHAPTER\s+(?P<number>[IVXLCDM]+)\.?"
    rf"(?:\s*[{_DASH}]\s*(?P<title>.+))?$",
    re.IGNORECASE,
)

# Chapter subsection labels (not Articles).
CHAPTER_SUBSECTION_RE = re.compile(
    r"^(?:"
    r"General|"
    r"The President and Vice-?President|"
    r"The Governor|"
    r"Conduct of Government Business|"
    r"Legislative Procedure|"
    r"Procedure in Financial Matters|"
    r"Procedure Generally|"
    r"Disqualifications of Members|"
    r"Officers of (?:the )?Parliament|"
    r"Powers[, ]+Privileges and Immunities of Parliament and its Members|"
    r"Distribution of Legislative Powers|"
    r"Distributionof Legislative Powers|"
    r"Administrative Relations|"
    r"Finance|"
    r"Miscellaneous Financial Provisions|"
    r"Borrowing|"
    r"Property[, ]+Contracts[, ]+Rights[, ]+Liabilities[, ]+Obligations and Suits|"
    r"Right to Property|"
    r"Services|"
    r"Public Service Commissions|"
    r"Language of the Union|"
    r"Regional Languages|"
    r"Language of the Supreme Court[, ]+High Courts[, ]+etc\.?|"
    r"Special Directives"
    r")\s*$",
    re.IGNORECASE,
)

# Optional leading footnote marker like 1[ before article number.
ARTICLE_HEADING_RE = re.compile(
    r"^(?P<fn_marker>\d+\s*\[)?"
    r"(?P<number>\d+[A-Za-z]{0,3})"
    r"\.\s*"
    r"(?P<title_and_body>.*)$"
)

ARTICLE_NUMBER_ONLY_RE = re.compile(
    r"^(?P<fn_marker>\d+\s*\[)?"
    r"(?P<number>\d+[A-Za-z]{0,3})"
    r"\.?\s*$"
)

OMITTED_RE = re.compile(
    r"^\[?\s*Omitted\.?\s*\]?\.?$",
    re.IGNORECASE,
)

REPEALED_RE = re.compile(
    r"^\[?\s*Repealed\.?\s*\]?\.?$",
    re.IGNORECASE,
)

CLAUSE_LABEL_RE = re.compile(
    r"^\((?P<label>\d+[A-Za-z]?|[a-z]|[ivxlcdm]+|[A-Z])\)\s*(?P<body>.*)$"
)

PROVISO_RE = re.compile(
    r"^(?P<text>Provided(?:\s+further|\s+also)?\s+that\b.*)$",
    re.IGNORECASE,
)

EXPLANATION_RE = re.compile(
    r"^(?P<label>Explanation(?:\s+[IVXLC\d]+)?)\s*[.—:\-]?\s*(?P<body>.*)$",
    re.IGNORECASE,
)

EXCEPTION_RE = re.compile(
    r"^(?P<label>Exception(?:\s+[IVXLC\d]+)?)\s*[.—:\-]?\s*(?P<body>.*)$",
    re.IGNORECASE,
)

ILLUSTRATION_RE = re.compile(
    r"^(?P<label>Illustration(?:\s+[IVXLC\d]+)?)\s*[.—:\-]?\s*(?P<body>.*)$",
    re.IGNORECASE,
)

FOOTNOTE_RE = re.compile(
    r"^(?P<marker>\d+)\.\s+(?P<text>.+)$"
)

FOOTNOTE_CONTINUATION_HINT_RE = re.compile(
    r"^(?:Subs\.|Ins\.|Omitted|Repealed|Added|Renumbered|The words?\b|w\.e\.f\.)",
    re.IGNORECASE,
)

# Allow glued titles: "EIGHTH SCHEDULELanguages." / trailing hyphen.
SCHEDULE_RE = re.compile(
    r"^(?:THE\s+)?"
    r"(?P<number>FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|"
    r"TENTH|ELEVENTH|TWELFTH|[IVXLCDM]+|\d+)"
    r"(?:TH|ST|ND|RD)?\s*SCHEDULE"
    rf"(?:\s*[{_DASH}\-]?\s*(?P<title>.+))?$",
    re.IGNORECASE,
)

PREAMBLE_RE = re.compile(r"^PREAMBLE\s*$", re.IGNORECASE)

APPENDIX_RE = re.compile(
    r"^(?:APPENDIX|ANNEXURE|APPENDICES)\s*(?P<label>[IVXLCDM\d]*)\s*\.?\s*"
    r"(?P<title>.*)$",
    re.IGNORECASE,
)

TITLE_BODY_SPLIT_RE = re.compile(
    rf"^(?P<title>.*?)\s*[{_DASH}]\s*(?P<body>.*)$"
)

# Also split on ".-" / ". -" diglot separators.
TITLE_DOT_DASH_BODY_RE = re.compile(
    r"^(?P<title>.+?)\.\s*[-—–⎯−]\s*(?P<body>.*)$"
)

TITLE_PERIOD_BODY_RE = re.compile(
    r"^(?P<title>[A-Z][^.]{0,200}\.)\s*(?P<body>[A-Z].*)$"
)

AMENDMENT_ACT_RE = re.compile(
    r"Constitution\s+\((?P<name>[^)]+Amendment)\)\s+Act,?\s*(?P<year>\d{4})",
    re.IGNORECASE,
)

AMENDMENT_ORDINAL_RE = re.compile(
    r"(?P<ordinal>First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth|"
    r"Eleventh|Twelfth|Thirteenth|Fourteenth|Fifteenth|Sixteenth|Seventeenth|"
    r"Eighteenth|Nineteenth|Twentieth|Twenty-first|Twenty-second|"
    r"Twenty-third|Twenty-fourth|Twenty-fifth|Twenty-sixth|Twenty-seventh|"
    r"Twenty-eighth|Twenty-ninth|Thirtieth|"
    r"Thirty-[a-z]+|Forty-[a-z]+|Fifty-[a-z]+|Sixty-[a-z]+|"
    r"Seventy-[a-z]+|Eighty-[a-z]+|Ninety-[a-z]+|"
    r"One Hundred(?:\s+and)?\s+[a-z\-]+)\s+Amendment",
    re.IGNORECASE,
)

OPERATION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("inserted", re.compile(r"\bIns\.?\b|\bInserted\b", re.IGNORECASE)),
    ("substituted", re.compile(r"\bSubs\.?\b|\bSubstituted\b", re.IGNORECASE)),
    ("omitted", re.compile(r"\bOmitted\b", re.IGNORECASE)),
    ("repealed", re.compile(r"\bRepealed\b", re.IGNORECASE)),
    ("renumbered", re.compile(r"\bRenumbered\b", re.IGNORECASE)),
    ("amended", re.compile(r"\bAmended\b", re.IGNORECASE)),
]

LIST_HEADING_RE = re.compile(
    r"^(?P<name>List\s*(?:I|II|III|1|2|3)\b.*)$",
    re.IGNORECASE,
)

ENACTMENT_DATE_RE = re.compile(
    r"^(?P<line>.*\b(?:twentieth|26th|twenty-sixth)\s+day\s+of\s+\w+.*\d{4}.*)$",
    re.IGNORECASE,
)

# Inline footnote marker references in body text: 1[, 2[, etc.
INLINE_FOOTNOTE_MARKER_RE = re.compile(r"(?<!\w)(\d+)\s*\[")
