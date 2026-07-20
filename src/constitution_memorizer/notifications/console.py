"""Console notifier for dry-run / local testing."""

from __future__ import annotations


class ConsoleNotifier:
    def send(self, title: str, body: str) -> None:
        print(f"=== {title} ===")
        print(body)
        print("=== end ===")
