"""Notifier protocol and factory."""

from __future__ import annotations

from typing import Protocol

from constitution_memorizer.notifications.console import ConsoleNotifier
from constitution_memorizer.notifications.macos import MacOSNotifier
from constitution_memorizer.notifications.ntfy import NtfyNotifier


class Notifier(Protocol):
    def send(self, title: str, body: str) -> None:
        """Deliver a notification."""


def get_notifier(channel: str) -> Notifier:
    name = (channel or "console").strip().lower()
    if name in {"console", "dry-run", "dry_run"}:
        return ConsoleNotifier()
    if name == "ntfy":
        return NtfyNotifier.from_env()
    if name in {"macos", "mac", "osascript"}:
        return MacOSNotifier()
    raise ValueError(
        f"Unknown reminder channel: {channel!r} (use console, ntfy, or macos)"
    )
