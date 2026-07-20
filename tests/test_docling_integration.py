"""Optional Docling integration test (skipped without PDF/Docling)."""

from __future__ import annotations

from pathlib import Path

import pytest

PDF_PATH = Path("data/input/constitution_bare_act.pdf")


@pytest.mark.integration
def test_docling_extract_smoke(tmp_path: Path) -> None:
    pytest.importorskip("docling")
    if not PDF_PATH.exists():
        pytest.skip("Bare Act PDF not present")

    from constitution_memorizer.extraction.docling_extractor import extract_pdf

    out = tmp_path / "data"
    metadata = extract_pdf(PDF_PATH, out, force=True)
    assert (out / "raw" / "constitution_docling.json").exists()
    assert (out / "intermediate" / "constitution.md").exists()
    assert metadata.source_sha256
    assert metadata.file_size_bytes > 0
