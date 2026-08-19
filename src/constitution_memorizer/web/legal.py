"""Public legal pages for Google OAuth branding and DPDP grievance access.

``/terms``, ``/privacy`` and ``/grievance`` are always public. Operator identity
fields stay empty until set in the environment — never invent a legal entity,
address, mailbox or Grievance Officer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

LEGAL_PATHS: tuple[str, ...] = ("/terms", "/privacy", "/grievance")

UNCONFIGURED = "Not yet configured"
EFFECTIVE_DATE = "20 August 2026"
LAST_UPDATED = "20 August 2026"
ACCOUNT_DELETION_PATH = "/profile"
GOOGLE_CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.app.created"
GOOGLE_USER_DATA_POLICY_URL = (
    "https://developers.google.com/terms/api-services-user-data-policy"
)

REQUIRED_LEGAL_FIELDS: tuple[tuple[str, str], ...] = (
    ("LEGAL_ENTITY_NAME", "legal_entity_name"),
    ("LEGAL_BUSINESS_ADDRESS", "legal_business_address"),
    ("LEGAL_SUPPORT_EMAIL", "legal_support_email"),
    ("LEGAL_PRIVACY_EMAIL", "legal_privacy_email"),
    ("LEGAL_GRIEVANCE_EMAIL", "legal_grievance_email"),
    ("LEGAL_GRIEVANCE_OFFICER", "legal_grievance_officer"),
    ("LEGAL_JURISDICTION", "legal_jurisdiction"),
)


@dataclass(frozen=True)
class LegalField:
    """A published value, or a visible unconfigured fallback."""

    value: str
    placeholder: str = UNCONFIGURED

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
    lede: str
    description: str
    template: str
    toc: tuple[tuple[str, str, str], ...]  # id, nn, label


TERMS = LegalPage(
    slug="terms",
    path="/terms",
    title="Terms & Conditions",
    eyebrow="Terms",
    lede="Rules for using Recall the C as a study aid for the Constitution of India.",
    description="Terms and Conditions governing use of Recall the C.",
    template="legal/terms.html",
    toc=(
        ("about", "01", "About Recall the C"),
        ("not-legal-advice", "02", "Educational purpose"),
        ("eligibility", "03", "Eligibility"),
        ("accounts", "04", "Accounts"),
        ("progress", "05", "Learning progress"),
        ("google-calendar", "06", "Google Calendar"),
        ("plans", "07", "Free and paid features"),
        ("payments", "08", "Payments"),
        ("ip", "09", "Intellectual property"),
        ("prohibited", "10", "Prohibited use"),
        ("feedback", "11", "Feedback"),
        ("availability", "12", "Availability"),
        ("accuracy", "13", "Accuracy"),
        ("third-parties", "14", "Third-party services"),
        ("termination", "15", "Suspension"),
        ("warranties", "16", "Disclaimer"),
        ("liability", "17", "Liability"),
        ("privacy", "18", "Privacy"),
        ("changes", "19", "Changes"),
        ("governing-law", "20", "Governing law"),
        ("contact", "21", "Contact"),
    ),
)

PRIVACY = LegalPage(
    slug="privacy",
    path="/privacy",
    title="Privacy Policy",
    eyebrow="Privacy",
    lede="How we collect, use and protect information when you use Recall the C.",
    description=(
        "How Recall the C collects, uses, stores and protects personal "
        "information and Google user data."
    ),
    template="legal/privacy.html",
    toc=(
        ("scope", "01", "Overview"),
        ("collect", "02", "Information we collect"),
        ("google-signin", "03", "Google Sign-In"),
        ("google-calendar", "04", "Google Calendar"),
        ("oauth-tokens", "05", "OAuth tokens"),
        ("use", "06", "How we use personal data"),
        ("consent", "07", "Consent and choices"),
        ("disconnect", "08", "Disconnecting Google Calendar"),
        ("managing-google-data", "09", "Managing your Google data"),
        ("sharing", "10", "Sharing of personal data"),
        ("google-sharing", "11", "Google user data sharing"),
        ("cookies", "12", "Cookies and sessions"),
        ("retention", "13", "Data retention"),
        ("deletion", "14", "Account deletion"),
        ("rights", "15", "Your privacy rights"),
        ("security", "16", "Security"),
        ("breaches", "17", "Personal data breaches"),
        ("international", "18", "International processing"),
        ("children", "19", "Children's privacy"),
        ("changes", "20", "Changes"),
        ("contact", "21", "Privacy contact"),
    ),
)

GRIEVANCE = LegalPage(
    slug="grievance",
    path="/grievance",
    title="Grievance Redressal",
    eyebrow="Grievance",
    lede="How to raise a concern about your account, personal data, or the Service.",
    description=(
        "How to submit a privacy, account, content or service grievance "
        "to Recall the C."
    ),
    template="legal/grievance.html",
    toc=(
        ("officer", "01", "Grievance Officer"),
        ("what", "02", "What you can report"),
        ("how", "03", "How to submit"),
        ("timelines", "04", "Acknowledgment and resolution"),
        ("privacy-requests", "05", "Privacy requests"),
        ("google", "06", "Google complaints"),
        ("security", "07", "Security incidents"),
        ("content", "08", "Content accuracy"),
        ("payments", "09", "Payments"),
        ("escalation", "10", "Escalation"),
        ("abuse", "11", "Abuse of this mechanism"),
        ("confidentiality", "12", "Confidentiality"),
        ("contact", "13", "Contact details"),
    ),
)

PAGES: dict[str, LegalPage] = {
    TERMS.slug: TERMS,
    PRIVACY.slug: PRIVACY,
    GRIEVANCE.slug: GRIEVANCE,
}


def _field(raw: str | None) -> LegalField:
    return LegalField(value=(raw or "").strip(), placeholder=UNCONFIGURED)


def operator_fields(settings: Any | None) -> dict[str, LegalField]:
    """Build template fields from optional multi-user settings."""

    def get(name: str) -> str:
        if settings is None:
            return ""
        return str(getattr(settings, name, "") or "").strip()

    return {
        "entity": _field(get("legal_entity_name")),
        "address": _field(get("legal_business_address")),
        "jurisdiction": _field(get("legal_jurisdiction")),
        "support_email": _field(get("legal_support_email")),
        "privacy_email": _field(get("legal_privacy_email")),
        "grievance_email": _field(get("legal_grievance_email")),
        "grievance_officer": _field(get("legal_grievance_officer")),
        "privacy_contact": _field(get("legal_privacy_contact")),
    }


def missing_legal_configuration(settings: Any | None) -> list[str]:
    """Env names that are still empty. Non-empty list is not Google-verification-ready."""
    missing: list[str] = []
    for env_name, attr in REQUIRED_LEGAL_FIELDS:
        value = ""
        if settings is not None:
            value = str(getattr(settings, attr, "") or "").strip()
        if not value:
            missing.append(env_name)
    return missing


def legal_page_context(slug: str, settings: Any | None) -> dict[str, Any]:
    page = PAGES[slug]
    return {
        "page": page,
        "pages": (TERMS, PRIVACY, GRIEVANCE),
        "op": operator_fields(settings),
        "effective_date": EFFECTIVE_DATE,
        "last_updated": LAST_UPDATED,
        "account_deletion_path": ACCOUNT_DELETION_PATH,
        "google_calendar_scope": GOOGLE_CALENDAR_SCOPE,
        "google_user_data_policy_url": GOOGLE_USER_DATA_POLICY_URL,
        "unconfigured": UNCONFIGURED,
        "missing_legal": missing_legal_configuration(settings),
    }
