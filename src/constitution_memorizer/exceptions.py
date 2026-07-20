"""Package-level exceptions for the extraction pipeline."""

from __future__ import annotations


class ConstitutionMemorizerError(Exception):
    """Base error for the Constitution Memorizer pipeline."""


class InputValidationError(ConstitutionMemorizerError):
    """Raised when an input path or file fails validation."""


class OverwriteRefusedError(ConstitutionMemorizerError):
    """Raised when an output file exists and overwrite was not requested."""


class ExtractionError(ConstitutionMemorizerError):
    """Raised when Docling PDF conversion fails."""


class NormalizationError(ConstitutionMemorizerError):
    """Raised when the normalization stage fails unrecoverably."""


class ParseError(ConstitutionMemorizerError):
    """Raised when the constitution parser fails unrecoverably."""


class ValidationPipelineError(ConstitutionMemorizerError):
    """Raised when validation cannot complete (e.g. invalid input JSON)."""
