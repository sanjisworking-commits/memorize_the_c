"""Native macOS Notification Center via osascript."""

from __future__ import annotations

import platform
import subprocess
from dataclasses import dataclass

# Notification Center truncates long bodies; keep digest readable.
_MAX_BODY_CHARS = 180


def _escape_applescript(value: str) -> str:
    """Escape a Python string for use inside an AppleScript double-quoted literal."""
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\n", "\\n")
    )


def truncate_notification_body(body: str, *, max_chars: int = _MAX_BODY_CHARS) -> str:
    text = body.strip()
    if len(text) <= max_chars:
        return text
    cut = text[: max_chars - 1].rstrip()
    # Prefer breaking on a line boundary when possible.
    nl = cut.rfind("\n")
    if nl >= max_chars // 2:
        cut = cut[:nl]
    return cut.rstrip() + "…"


@dataclass(frozen=True)
class MacOSNotifier:
    """Deliver banners through macOS Notification Center (`osascript`)."""

    def send(self, title: str, body: str) -> None:
        if platform.system() != "Darwin":
            raise RuntimeError(
                "macos channel requires macOS (Darwin); "
                f"this host is {platform.system()!r}"
            )
        safe_title = _escape_applescript(title.strip() or "Recall the C")
        safe_body = _escape_applescript(truncate_notification_body(body))
        script = (
            f'display notification "{safe_body}" with title "{safe_title}"'
        )
        try:
            completed = subprocess.run(
                ["/usr/bin/osascript", "-e", script],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("osascript not found at /usr/bin/osascript") from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("osascript timed out") from exc
        if completed.returncode != 0:
            err = (completed.stderr or completed.stdout or "").strip()
            raise RuntimeError(
                f"osascript failed ({completed.returncode}): {err or 'unknown error'}"
            )
