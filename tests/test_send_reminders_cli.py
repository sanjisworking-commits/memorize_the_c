"""Sprint 24 — send-reminders CLI."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from constitution_memorizer.cli import main
from constitution_memorizer.progress.scheduler import ReminderEngine

MINI_UNITS = Path(__file__).parent / "fixtures" / "learning" / "mini_units.json"


def test_send_reminders_dry_run_console(tmp_path: Path, capsys):
    db = tmp_path / "progress.db"
    engine = ReminderEngine.from_paths(db, MINI_UNITS)
    engine.mark_done("clause-1", as_of=date(2026, 7, 19))
    code = main(
        [
            "send-reminders",
            "--channel",
            "console",
            "--dry-run",
            "--as-of",
            "2026-07-20",
            "--units",
            str(MINI_UNITS),
            "--db",
            str(db),
            "--output-dir",
            str(tmp_path),
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "due today" in out
    assert "Article 20(1)" in out


def test_send_reminders_skips_when_empty(tmp_path: Path, capsys):
    db = tmp_path / "progress.db"
    ReminderEngine.from_paths(db, MINI_UNITS)
    code = main(
        [
            "send-reminders",
            "--channel",
            "console",
            "--as-of",
            "2026-07-20",
            "--units",
            str(MINI_UNITS),
            "--db",
            str(db),
            "--output-dir",
            str(tmp_path),
        ]
    )
    assert code == 0
    assert "nothing due" in capsys.readouterr().out


def test_ntfy_notifier_posts(monkeypatch):
    from constitution_memorizer.notifications.ntfy import NtfyNotifier

    monkeypatch.setenv("NTFY_TOPIC", "test-topic")
    monkeypatch.setenv("NTFY_SERVER", "https://ntfy.example")
    notifier = NtfyNotifier.from_env()

    captured: dict = {}

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout=30):
        captured["url"] = request.full_url
        captured["data"] = request.data
        captured["title"] = request.headers.get("Title") or request.get_header("Title")
        return FakeResponse()

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        notifier.send("Hello", "Body line")
    assert captured["url"] == "https://ntfy.example/test-topic"
    assert captured["data"] == b"Body line"
