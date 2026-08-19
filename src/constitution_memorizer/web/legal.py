"""Public legal pages for Google OAuth branding and DPDP grievance access.

``/terms``, ``/privacy`` and ``/grievance`` are always public. Operator identity
fields that we must not invent (legal entity, address, jurisdiction, named
Grievance Officer) stay empty until set in the environment.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

LEGAL_PATHS: tuple[str, ...] = ("/terms", "/privacy", "/grievance")

DEFAULT_SUPPORT_EMAIL = "support@recall-the-c.in"
DEFAULT_PRIVACY_EMAIL = "privacy@recall-the-c.in"
DEFAULT_GRIEVANCE_EMAIL = "grievance@recall-the-c.in"
DEFAULT_PRIVACY_CONTACT = "Privacy Contact"
EFFECTIVE_DATE = "19 August 2026"
ACCOUNT_DELETION_PATH = "/profile"
GOOGLE_CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.app.created"
GOOGLE_USER_DATA_POLICY_URL = (
    "https://developers.google.com/terms/api-services-user-data-policy"
)


@dataclass(frozen=True)
class LegalField:
    """A published value, or a visible placeholder when unset."""

    value: str
    placeholder: str

    @property
    def set(self) -> bool:
        return bool(self.value.strip())

    @property
    def display(self) -> str:
        return self.value.strip() if self.set else self.placeholder


@dataclass(frozen=True)
class LegalPage:
    slug: str
    path: str
    title: str
    eyebrow: str
    description: str
    partial: str
    toc: tuple[tuple[str, str], ...]


TERMS = LegalPage(
    slug="terms",
    path="/terms",
    title="Terms & Conditions",
    eyebrow="Terms",
    description=(
        "Terms governing your use of Recall the C, including accounts, "
        "Google Calendar, payments and educational-purpose limits."
    ),
    partial="_legal_terms.html",
    toc=(
        ("about", "1. About Recall the C"),
        ("not-legal-advice", "2. Educational purpose"),
        ("eligibility", "3. Eligibility"),
        ("accounts", "4. Accounts"),
        ("progress", "5. Learning progress"),
        ("google-calendar", "6. Google Calendar"),
        ("plans", "7. Free and paid features"),
        ("payments", "8. Payments"),
        ("ip", "9. Intellectual property"),
        ("prohibited", "10. Prohibited use"),
        ("feedback", "11. Feedback"),
        ("availability", "12. Availability"),
        ("accuracy", "13. Accuracy"),
        ("third-parties", "14. Third-party services"),
        ("termination", "15. Suspension"),
        ("warranties", "16. Disclaimer"),
        ("liability", "17. Liability"),
        ("privacy", "18. Privacy"),
        ("changes", "19. Changes"),
        ("governing-law", "20. Governing law"),
        ("contact", "21. Contact"),
    ),
)

PRIVACY = LegalPage(
    slug="privacy",
    path="/privacy",
    title="Privacy Policy",
    eyebrow="Privacy",
    description=(
        "How Recall the C collects, uses and stores personal data, including "
        "Google Sign-In and optional Google Calendar information."
    ),
    partial="_legal_privacy.html",
    toc=(
        ("scope", "1. Scope"),
        ("collect", "2. Information we may collect"),
        ("google-signin", "3. Google Sign-In"),
        ("google-calendar", "4. Google Calendar data"),
        ("oauth-tokens", "5. OAuth tokens"),
        ("use", "6. How we use personal data"),
        ("consent", "7. Consent and choices"),
        ("disconnect", "8. Disconnecting Google Calendar"),
        ("sharing", "9. Sharing of personal data"),
        ("google-sharing", "10. Google user data sharing"),
        ("cookies", "11. Cookies and sessions"),
        ("retention", "12. Data retention"),
        ("deletion", "13. Account deletion"),
        ("rights", "14. Your privacy rights"),
        ("security", "15. Security"),
        ("breaches", "16. Personal data breaches"),
        ("international", "17. International processing"),
        ("children", "18. Children's privacy"),
        ("changes", "19. Changes"),
        ("contact", "20. Privacy contact"),
    ),
)

GRIEVANCE = LegalPage(
    slug="grievance",
    path="/grievance",
    title="Grievance Redressal",
    eyebrow="Grievance",
    description=(
        "How to raise a concern about your Recall the C account, personal data, "
        "Google integrations, payments or educational content."
    ),
    partial="_legal_grievance.html",
    toc=(
        ("officer", "1. Grievance Officer"),
        ("what", "2. What you can report"),
        ("how", "3. How to submit"),
        ("timelines", "4. Acknowledgment and resolution"),
        ("privacy-requests", "5. Privacy requests"),
        ("google", "6. Google complaints"),
        ("security", "7. Security incidents"),
        ("content", "8. Content accuracy"),
        ("payments", "9. Payments"),
        ("escalation", "10. Escalation"),
        ("abuse", "11. Abuse of this mechanism"),
        ("confidentiality", "12. Confidentiality"),
        ("contact", "13. Contact details"),
    ),
)

PAGES: dict[str, LegalPage] = {
    TERMS.slug: TERMS,
    PRIVACY.slug: PRIVACY,
    GRIEVANCE.slug: GRIEVANCE,
}


def _field(raw: str | None, placeholder: str) -> LegalField:
    return LegalField(value=(raw or "").strip(), placeholder=placeholder)


def operator_fields(settings: Any | None) -> dict[str, LegalField]:
    """Build template fields from optional multi-user settings."""

    def get(name: str, default: str = "") -> str:
        if settings is None:
            return default
        return str(getattr(settings, name, default) or default).strip()

    return {
        "entity": _field(get("legal_entity_name"), "[LEGAL ENTITY / PROPRIETOR NAME]"),
        "address": _field(get("legal_business_address"), "[BUSINESS ADDRESS]"),
        "jurisdiction": _field(get("legal_jurisdiction"), "[CITY, STATE, INDIA]"),
        "support_email": _field(
            get("legal_support_email", DEFAULT_SUPPORT_EMAIL),
            "[SUPPORT EMAIL]",
        ),
        "privacy_email": _field(
            get("legal_privacy_email", DEFAULT_PRIVACY_EMAIL),
            "[PRIVACY EMAIL]",
        ),
        "grievance_email": _field(
            get("legal_grievance_email", DEFAULT_GRIEVANCE_EMAIL),
            "[GRIEVANCE EMAIL]",
        ),
        "grievance_officer": _field(get("legal_grievance_officer"), "[FULL NAME]"),
        "privacy_contact": _field(
            get("legal_privacy_contact", DEFAULT_PRIVACY_CONTACT),
            "[NAME OR ROLE]",
        ),
    }


def legal_page_context(slug: str, settings: Any | None) -> dict[str, Any]:
    page = PAGES[slug]
    return {
        "page": page,
        "pages": (TERMS, PRIVACY, GRIEVANCE),
        "op": operator_fields(settings),
        "effective_date": EFFECTIVE_DATE,
        "account_deletion_path": ACCOUNT_DELETION_PATH,
        "google_calendar_scope": GOOGLE_CALENDAR_SCOPE,
        "google_user_data_policy_url": GOOGLE_USER_DATA_POLICY_URL,
    }
