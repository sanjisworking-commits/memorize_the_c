"""In-process rate limiting for OTP routes (replaceable in production)."""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field

from constitution_memorizer.auth.exceptions import RateLimitError


@dataclass
class _Bucket:
    events: list[float] = field(default_factory=list)
    last_sent: float = 0.0
    verify_failures: int = 0


class OtpRateLimiter:
    """Per-IP and per-phone OTP protections."""

    def __init__(
        self,
        *,
        per_phone_limit: int = 5,
        per_ip_limit: int = 20,
        window_seconds: float = 3600.0,
        resend_cooldown_seconds: float = 30.0,
        max_verify_attempts: int = 5,
    ) -> None:
        self.per_phone_limit = per_phone_limit
        self.per_ip_limit = per_ip_limit
        self.window_seconds = window_seconds
        self.resend_cooldown_seconds = resend_cooldown_seconds
        self.max_verify_attempts = max_verify_attempts
        self._by_phone: dict[str, _Bucket] = defaultdict(_Bucket)
        self._by_ip: dict[str, _Bucket] = defaultdict(_Bucket)

    def _prune(self, bucket: _Bucket, now: float) -> None:
        cutoff = now - self.window_seconds
        bucket.events = [t for t in bucket.events if t >= cutoff]

    def check_send(self, *, phone: str, ip: str) -> None:
        now = time.monotonic()
        phone_b = self._by_phone[phone]
        ip_b = self._by_ip[ip]
        self._prune(phone_b, now)
        self._prune(ip_b, now)
        if phone_b.last_sent and (now - phone_b.last_sent) < self.resend_cooldown_seconds:
            raise RateLimitError("Please wait before requesting another code.")
        if len(phone_b.events) >= self.per_phone_limit:
            raise RateLimitError("Too many code requests. Try again later.")
        if len(ip_b.events) >= self.per_ip_limit:
            raise RateLimitError("Too many code requests. Try again later.")

    def record_send(self, *, phone: str, ip: str) -> None:
        now = time.monotonic()
        phone_b = self._by_phone[phone]
        ip_b = self._by_ip[ip]
        phone_b.events.append(now)
        phone_b.last_sent = now
        phone_b.verify_failures = 0
        ip_b.events.append(now)

    def check_verify(self, *, phone: str) -> None:
        phone_b = self._by_phone[phone]
        if phone_b.verify_failures >= self.max_verify_attempts:
            raise RateLimitError("Too many verification attempts. Request a new code.")

    def record_verify_failure(self, *, phone: str) -> None:
        self._by_phone[phone].verify_failures += 1

    def record_verify_success(self, *, phone: str) -> None:
        self._by_phone[phone].verify_failures = 0
