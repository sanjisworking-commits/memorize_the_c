"""Docling PDF extraction layer.

Converts a Bare Act PDF into lossless Docling JSON and Markdown without
modifying Docling's raw structural output.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version as pkg_version
from pathlib import Path
from typing import Any

from constitution_memorizer.exceptions import ExtractionError, InputValidationError
from constitution_memorizer.schemas import ExtractionMetadata
from constitution_memorizer.utils.json_io import write_json, write_text

logger = logging.getLogger(__name__)


def compute_sha256(path: Path) -> str:
    """Compute the SHA-256 hex digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_pdf_path(pdf_path: Path) -> Path:
    """Validate that ``pdf_path`` exists and looks like a PDF."""
    if not pdf_path.exists():
        raise InputValidationError(f"PDF not found: {pdf_path}")
    if not pdf_path.is_file():
        raise InputValidationError(f"PDF path is not a file: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise InputValidationError(f"Input must be a PDF file: {pdf_path}")
    return pdf_path.resolve()


def _resolve_docling_version() -> str | None:
    try:
        return pkg_version("docling")
    except PackageNotFoundError:
        return None


def _extract_page_count(conversion_result: Any, document: Any) -> int | None:
    """Best-effort page count from Docling conversion result."""
    for attr in ("pages", "page_count", "num_pages"):
        value = getattr(conversion_result, attr, None)
        if isinstance(value, int):
            return value
        if isinstance(value, list):
            return len(value)

    input_obj = getattr(conversion_result, "input", None)
    if input_obj is not None:
        for attr in ("page_count", "pages"):
            value = getattr(input_obj, attr, None)
            if isinstance(value, int):
                return value
            if isinstance(value, list):
                return len(value)

    pages = getattr(document, "pages", None)
    if isinstance(pages, dict):
        return len(pages)
    if isinstance(pages, list):
        return len(pages)

    # Fallback: inspect exported dict
    try:
        exported = document.export_to_dict()
        if isinstance(exported, dict):
            if "pages" in exported and isinstance(exported["pages"], (list, dict)):
                return len(exported["pages"])
            meta = exported.get("metadata") or exported.get("origin") or {}
            if isinstance(meta, dict):
                for key in ("page_count", "pages_count", "num_pages"):
                    if isinstance(meta.get(key), int):
                        return meta[key]
    except Exception:  # noqa: BLE001 — best-effort only
        logger.debug("Could not derive page count from export_to_dict", exc_info=True)

    return None


def _detect_ocr_used(conversion_result: Any) -> bool | None:
    """Return whether OCR appears to have been used, if discoverable."""
    for attr in ("ocr_used", "used_ocr", "do_ocr"):
        value = getattr(conversion_result, attr, None)
        if isinstance(value, bool):
            return value

    status = getattr(conversion_result, "status", None)
    if status is not None:
        value = getattr(status, "ocr_used", None)
        if isinstance(value, bool):
            return value

    return None


def _collect_warnings(conversion_result: Any) -> list[str]:
    """Collect string warnings from a Docling conversion result."""
    warnings: list[str] = []
    raw_warnings = getattr(conversion_result, "warnings", None)
    if isinstance(raw_warnings, list):
        for item in raw_warnings:
            warnings.append(str(item))
    errors = getattr(conversion_result, "errors", None)
    if isinstance(errors, list):
        for item in errors:
            msg = getattr(item, "error_message", None) or str(item)
            warnings.append(f"conversion_error: {msg}")
    return warnings


def ensure_data_dirs(output_dir: Path) -> dict[str, Path]:
    """Create standard data subdirectories under ``output_dir``."""
    dirs = {
        "raw": output_dir / "raw",
        "intermediate": output_dir / "intermediate",
        "output": output_dir / "output",
        "rejected": output_dir / "rejected",
        "input": output_dir / "input",
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs


def extract_pdf(
    pdf_path: Path,
    output_dir: Path,
    *,
    force: bool = False,
) -> ExtractionMetadata:
    """
    Extract a PDF with Docling and write raw JSON + Markdown.

    Parameters
    ----------
    pdf_path:
        Path to the Bare Act PDF.
    output_dir:
        Root data directory (typically ``data/``).
    force:
        Overwrite existing extraction outputs when True.
    """
    pdf_path = validate_pdf_path(pdf_path)
    output_dir = output_dir.resolve()
    dirs = ensure_data_dirs(output_dir)

    raw_json_path = dirs["raw"] / "constitution_docling.json"
    markdown_path = dirs["intermediate"] / "constitution.md"
    metadata_path = dirs["raw"] / "extraction_metadata.json"

    file_size = pdf_path.stat().st_size
    sha256 = compute_sha256(pdf_path)
    extracted_at = datetime.now(timezone.utc).isoformat()

    logger.info("Starting Docling extraction for %s", pdf_path)
    logger.info("File size=%s bytes sha256=%s", file_size, sha256)

    try:
        from docling.document_converter import DocumentConverter
    except ImportError as exc:
        raise ExtractionError(
            "Docling is not installed. Install dependencies with: "
            "pip install -r requirements.txt"
        ) from exc

    try:
        converter = DocumentConverter()
        result = converter.convert(str(pdf_path))
    except Exception as exc:  # noqa: BLE001 — wrap third-party failures
        logger.exception("Docling conversion failed")
        raise ExtractionError(f"Docling conversion failed: {exc}") from exc

    document = getattr(result, "document", None)
    if document is None:
        raise ExtractionError("Docling conversion returned no document")

    try:
        raw_dict = document.export_to_dict()
        markdown = document.export_to_markdown()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to export Docling document")
        raise ExtractionError(f"Failed to export Docling document: {exc}") from exc

    if not isinstance(raw_dict, dict):
        raise ExtractionError("Docling export_to_dict did not return a dictionary")
    if not isinstance(markdown, str):
        raise ExtractionError("Docling export_to_markdown did not return a string")

    page_count = _extract_page_count(result, document)
    ocr_used = _detect_ocr_used(result)
    warnings = _collect_warnings(result)
    docling_version = _resolve_docling_version()

    write_json(raw_json_path, raw_dict, force=force, indent=2)
    write_text(markdown_path, markdown if markdown.endswith("\n") else markdown + "\n", force=force)

    metadata = ExtractionMetadata(
        source_filename=pdf_path.name,
        source_path=str(pdf_path),
        file_size_bytes=file_size,
        source_sha256=sha256,
        extracted_at=extracted_at,
        page_count=page_count,
        docling_version=docling_version,
        ocr_used=ocr_used,
        output_paths={
            "raw_json": str(raw_json_path),
            "markdown": str(markdown_path),
            "metadata": str(metadata_path),
        },
        warnings=warnings,
    )
    write_json(metadata_path, metadata.model_dump(mode="json"), force=force, indent=2)

    logger.info(
        "Extraction complete: pages=%s warnings=%s outputs=%s",
        page_count,
        len(warnings),
        metadata.output_paths,
    )
    return metadata
