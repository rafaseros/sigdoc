"""PDF infrastructure package.

Provides the GotenbergPdfConverter adapter and a cached factory function
that wires it to the application settings.

Design: ADR-PDF-01, ADR-PDF-02
"""
from functools import lru_cache

from app.domain.ports.pdf_converter import PdfConverter


@lru_cache
def get_pdf_converter() -> PdfConverter:
    """Return a singleton GotenbergPdfConverter configured from Settings.

    Cached via @lru_cache so the same instance is reused across requests
    (mirrors the pattern used by get_storage_service).
    """
    from app.config import get_settings
    from app.infrastructure.pdf.gotenberg_pdf_converter import GotenbergPdfConverter

    settings = get_settings()
    return GotenbergPdfConverter(
        gotenberg_url=settings.gotenberg_url,
        timeout=settings.gotenberg_timeout,
    )
