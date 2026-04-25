"""Unit tests for PdfConversionError — T-DOMAIN-03.

Tests must FAIL (red) before PdfConversionError is added to exceptions.py.
"""
import pytest


def test_pdf_conversion_error_is_domain_error() -> None:
    """PdfConversionError must extend DomainError (REQ-PDF-06)."""
    from app.domain.exceptions import DomainError, PdfConversionError

    assert issubclass(PdfConversionError, DomainError)


def test_pdf_conversion_error_accepts_message() -> None:
    """PdfConversionError must accept a descriptive message string (REQ-PDF-06)."""
    from app.domain.exceptions import PdfConversionError

    exc = PdfConversionError("Gotenberg returned 500")
    assert str(exc) == "Gotenberg returned 500"


def test_pdf_conversion_error_is_exception() -> None:
    """PdfConversionError must be raise-able as a standard exception."""
    from app.domain.exceptions import PdfConversionError

    with pytest.raises(PdfConversionError, match="forced failure"):
        raise PdfConversionError("forced failure")
