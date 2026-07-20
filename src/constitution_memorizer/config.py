"""Configuration for extraction, normalization and parsing thresholds."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_KNOWN_HEADERS: list[str] = [
    "THE CONSTITUTION OF INDIA",
    "Constitution of India",
    "CONSTITUTION OF INDIA",
]


@dataclass
class PipelineConfig:
    """Runtime configuration for the PDF-to-JSON pipeline."""

    known_headers: list[str] = field(default_factory=lambda: list(DEFAULT_KNOWN_HEADERS))
    known_footer_patterns: list[str] = field(
        default_factory=lambda: [
            r"^https?://",
            r"^www\.",
            r"^Legislative Department",
            r"^Ministry of Law",
            r"^Government of India$",
        ]
    )
    minimum_header_page_frequency: float = 0.6
    near_duplicate_threshold: float = 0.96
    preserve_raw_text: bool = True
    include_bounding_boxes: bool = True
    min_header_length: int = 8
    max_page_number_digits: int = 4
    schema_version: str = "1.0.0"

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary of this config."""
        return asdict(self)


def default_config() -> PipelineConfig:
    """Return a fresh default configuration instance."""
    return PipelineConfig()


def load_config(path: Path | None = None) -> PipelineConfig:
    """
    Load configuration from an optional JSON file.

    Missing keys fall back to defaults. Unknown keys are ignored with a warning.
    """
    config = default_config()
    if path is None:
        return config

    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, dict):
        raise ValueError(f"Config file must contain a JSON object: {path}")

    known_fields = {f.name for f in config.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    for key, value in data.items():
        if key not in known_fields:
            logger.warning("Ignoring unknown config key: %s", key)
            continue
        setattr(config, key, value)

    logger.info("Loaded configuration from %s", path)
    return config
