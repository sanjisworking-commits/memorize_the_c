"""Razorpay Standard Checkout — order creation and signature verification.

Server-side only. The key secret is used here for Basic-auth order creation
and HMAC verification and never reaches a template, JSON payload, or client
script; the public key id is the only credential the checkout page sees.

Amounts are always derived server-side from the pricing catalog (the client
sends a plan's days, never a price). A verified payment marks the order paid
and inserts a 'payment'-source access_grants row in one repository
transaction, so has_active_recall_access() keeps answering from one place.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

RAZORPAY_ORDERS_URL = "https://api.razorpay.com/v1/orders"
# Razorpay's minimum chargeable amount.
MIN_AMOUNT_PAISE = 100


class BillingError(RuntimeError):
    """Order creation failed (auth or Razorpay API error)."""

    def __init__(self, message: str, *, status_code: int = 500) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class RazorpayOrder:
    order_id: str
    amount_paise: int
    currency: str


def billing_enabled(app_state: object) -> bool:
    """Checkout is live only when both keys are configured (and pricing is on)."""
    return bool(
        getattr(app_state, "pricing_enabled", False)
        and getattr(app_state, "razorpay_key_id", "")
        and getattr(app_state, "razorpay_key_secret", "")
    )


def create_order(
    *,
    key_id: str,
    key_secret: str,
    amount_paise: int,
    receipt: str,
    currency: str = "INR",
) -> RazorpayOrder:
    """Create a Razorpay order (server-to-server, Basic auth)."""
    if amount_paise < MIN_AMOUNT_PAISE:
        raise BillingError(
            f"Amount below Razorpay minimum ({MIN_AMOUNT_PAISE} paise)",
            status_code=400,
        )
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.post(
                RAZORPAY_ORDERS_URL,
                auth=(key_id, key_secret),
                json={
                    "amount": amount_paise,
                    "currency": currency,
                    "receipt": receipt,
                },
            )
    except httpx.HTTPError as exc:  # network failure, timeout, DNS…
        logger.exception("Razorpay order request failed")
        raise BillingError("Could not reach the payment provider") from exc
    if response.status_code == 401:
        logger.error("Razorpay rejected the API credentials")
        raise BillingError("Payment provider authentication failed", status_code=401)
    if response.status_code >= 400:
        logger.error(
            "Razorpay order creation failed: %s %s",
            response.status_code,
            response.text[:500],
        )
        raise BillingError("Payment provider rejected the order")
    data = response.json()
    return RazorpayOrder(
        order_id=str(data["id"]),
        amount_paise=int(data["amount"]),
        currency=str(data["currency"]),
    )


def verify_signature(
    *,
    order_id: str,
    payment_id: str,
    signature: str,
    key_secret: str,
) -> bool:
    """Constant-time check of Razorpay's payment signature.

    HMAC-SHA256 over ``order_id|payment_id`` with the key secret must equal
    the signature Checkout handed to the client. A mismatch means the
    payment must NOT be marked paid.
    """
    if not (order_id and payment_id and signature):
        return False
    expected = hmac.new(
        key_secret.encode("utf-8"),
        f"{order_id}|{payment_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
