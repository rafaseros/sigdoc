"""Gotenberg PDF converter adapter.

Implements the PdfConverter port using the Gotenberg LibreOffice conversion
endpoint.  Uses httpx.AsyncClient for non-blocking I/O consistent with the
rest of the application.

Design: ADR-PDF-01, ADR-PDF-02
REQs: REQ-PDF-02, REQ-PDF-08, REQ-PDF-09, REQ-PDF-10
"""
import logging
import time

import httpx

from app.domain.exceptions import PdfConversionError
from app.domain.ports.pdf_converter import PdfConverter

logger = logging.getLogger(__name__)

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class GotenbergPdfConverter(PdfConverter):
    """Convert DOCX bytes to PDF bytes via Gotenberg's LibreOffice endpoint.

    A new httpx.AsyncClient is created per call — no connection pooling in v1
    because Gotenberg's bottleneck is LibreOffice conversion, not TCP setup.

    Args:
        gotenberg_url: Base URL of the Gotenberg service (no trailing slash).
        timeout: Maximum seconds to wait for the conversion response.
                 Maps to httpx read timeout; connect timeout is fixed at 5s.
    """

    def __init__(self, gotenberg_url: str, timeout: int = 60) -> None:
        self._convert_url = f"{gotenberg_url}/forms/libreoffice/convert"
        self._timeout = httpx.Timeout(
            connect=5.0,
            read=float(timeout),
            write=10.0,
            pool=5.0,
        )

    async def convert(self, docx_bytes: bytes) -> bytes:
        """Convert DOCX bytes to PDF bytes.

        Args:
            docx_bytes: Raw bytes of the .docx file to convert.

        Returns:
            Raw PDF bytes.

        Raises:
            PdfConversionError: On empty input, HTTP error, connection failure,
                                or timeout. Production code MUST NOT catch this
                                exception silently — it propagates to the
                                presentation layer and maps to HTTP 503.
        """
        if not docx_bytes:
            raise PdfConversionError("Cannot convert empty DOCX bytes to PDF")

        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    self._convert_url,
                    files={
                        "files": (
                            "document.docx",
                            docx_bytes,
                            DOCX_MIME,
                        )
                    },
                )
        except httpx.TimeoutException as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            msg = f"Gotenberg conversion timed out after {elapsed_ms}ms: {exc}"
            logger.error(msg)
            raise PdfConversionError(msg) from exc
        except httpx.ConnectError as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            msg = f"Gotenberg connection error after {elapsed_ms}ms: {exc}"
            logger.error(msg)
            raise PdfConversionError(msg) from exc
        except httpx.HTTPError as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            msg = f"Gotenberg HTTP error after {elapsed_ms}ms: {exc}"
            logger.error(msg)
            raise PdfConversionError(msg) from exc

        elapsed_ms = int((time.monotonic() - start) * 1000)

        if not response.is_success:
            msg = f"Gotenberg returned HTTP {response.status_code} after {elapsed_ms}ms"
            logger.error(msg)
            raise PdfConversionError(msg)

        pdf_bytes = response.content
        logger.info(
            "Gotenberg PDF conversion succeeded: %d bytes in %dms",
            len(pdf_bytes),
            elapsed_ms,
        )
        return pdf_bytes
