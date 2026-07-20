"""ntfy.sh (or self-hosted) HTTP push notifier."""

from __future__ import annotations

import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from email.header import Header


@dataclass(frozen=True)
class NtfyNotifier:
    server: str
    topic: str
    token: str | None = None

    @classmethod
    def from_env(cls) -> NtfyNotifier:
        topic = (os.environ.get("NTFY_TOPIC") or "").strip()
        if not topic:
            raise ValueError(
                "NTFY_TOPIC is required for --channel ntfy "
                "(set a private topic name, then subscribe in the ntfy app)"
            )
        server = (os.environ.get("NTFY_SERVER") or "https://ntfy.sh").rstrip("/")
        token = (os.environ.get("NTFY_TOKEN") or "").strip() or None
        return cls(server=server, topic=topic, token=token)

    def send(self, title: str, body: str) -> None:
        url = f"{self.server}/{self.topic}"
        data = body.encode("utf-8")
        # HTTP headers must be latin-1; encode non-ASCII titles safely.
        safe_title = str(Header(title, "utf-8"))
        headers = {
            "Title": safe_title,
            "Content-Type": "text/plain; charset=utf-8",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                if int(getattr(response, "status", 200)) >= 400:
                    raise RuntimeError(f"ntfy HTTP {response.status}")
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"ntfy HTTP {exc.code}: {exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"ntfy request failed: {exc.reason}") from exc
