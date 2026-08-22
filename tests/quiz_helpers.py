"""Helpers for completing Learn modes in tests.

Cloze/Letters/Type/Recite complete via POST /seen.
Test completes only via POST /quiz.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from constitution_memorizer.learning.schemas import LearningUnit, LearningUnitsDocument
from constitution_memorizer.web.quiz import build_quiz

SEEN_MODES = ("read", "cloze", "letters", "type", "recite")


def load_units(units_path: Path | str) -> dict[str, LearningUnit]:
    doc = LearningUnitsDocument.model_validate(
        json.loads(Path(units_path).read_text(encoding="utf-8"))
    )
    return {u.id: u for u in doc.units}


def correct_quiz_answers(
    units_path: Path | str, unit_id: str, cycle: int = 0
) -> list[object]:
    units = load_units(units_path)
    questions = build_quiz(units[unit_id], units, cycle=cycle)
    return [
        q.answer_index if q.kind == "mcq" else q.answer_text for q in questions
    ]


def current_quiz_cycle(client, unit_id: str) -> int:
    """Read the unit's current cycle off the learn page."""
    html = client.get(f"/learn/{unit_id}?mode=test").text
    match = re.search(r'data-quiz-cycle="(\d+)"', html)
    return int(match.group(1)) if match else 0


def submit_quiz(client, units_path: Path | str, unit_id: str, cycle: int | None = None):
    if cycle is None:
        cycle = current_quiz_cycle(client, unit_id)
    return client.post(
        f"/learn/{unit_id}/quiz",
        json={
            "cycle": cycle,
            "answers": correct_quiz_answers(units_path, unit_id, cycle),
        },
    )


def complete_all_modes(client, units_path: Path | str, unit_id: str):
    """Mark every learn mode complete: /seen for five modes, /quiz for Test.

    Entitlement-locked modes bounce with 403 mode_locked — that's the
    server refusing to record them, which is exactly what cap-reached
    scenarios exercise, so it is tolerated here.
    """
    last = None
    for mode in SEEN_MODES:
        resp = client.post(f"/learn/{unit_id}/seen", data={"mode": mode})
        assert resp.status_code in (200, 403), (mode, resp.status_code)
        last = resp
    quiz = submit_quiz(client, units_path, unit_id)
    assert quiz.status_code in (200, 400, 403), quiz.status_code
    return last if quiz.status_code != 200 else quiz
