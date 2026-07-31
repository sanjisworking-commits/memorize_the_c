"""Native macOS notifier (osascript) — mocked subprocess."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from constitution_memorizer.notifications.base import get_notifier
from constitution_memorizer.notifications.macos import (
    MacOSNotifier,
    truncate_notification_body,
    _escape_applescript,
)


def test_get_notifier_macos():
    assert isinstance(get_notifier("macos"), MacOSNotifier)
    assert isinstance(get_notifier("mac"), MacOSNotifier)


def test_escape_applescript_quotes_and_newlines():
    assert _escape_applescript('say "hi"') == 'say \\"hi\\"'
    assert _escape_applescript("a\nb") == "a\\nb"


def test_truncate_notification_body():
    short = "hello"
    assert truncate_notification_body(short) == short
    long = "line1\n" + ("x" * 200)
    out = truncate_notification_body(long, max_chars=40)
    assert len(out) <= 40
    assert out.endswith("…")


def test_macos_notifier_calls_osascript(monkeypatch):
    monkeypatch.setattr(
        "constitution_memorizer.notifications.macos.platform.system",
        lambda: "Darwin",
    )
    completed = MagicMock(returncode=0, stderr="", stdout="")
    with patch(
        "constitution_memorizer.notifications.macos.subprocess.run",
        return_value=completed,
    ) as run:
        MacOSNotifier().send('Title "A"', "Body\nline")
    assert run.call_count == 1
    args = run.call_args.args[0]
    assert args[0] == "/usr/bin/osascript"
    assert args[1] == "-e"
    script = args[2]
    assert 'with title "Title \\"A\\""' in script
    assert "display notification" in script


def test_macos_notifier_rejects_non_darwin(monkeypatch):
    monkeypatch.setattr(
        "constitution_memorizer.notifications.macos.platform.system",
        lambda: "Linux",
    )
    with pytest.raises(RuntimeError, match="requires macOS"):
        MacOSNotifier().send("t", "b")


def test_macos_notifier_raises_on_osascript_failure(monkeypatch):
    monkeypatch.setattr(
        "constitution_memorizer.notifications.macos.platform.system",
        lambda: "Darwin",
    )
    completed = MagicMock(returncode=1, stderr="boom", stdout="")
    with patch(
        "constitution_memorizer.notifications.macos.subprocess.run",
        return_value=completed,
    ):
        with pytest.raises(RuntimeError, match="osascript failed"):
            MacOSNotifier().send("t", "b")
