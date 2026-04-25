"""Domain port: PdfConverter.

Defines the abstract interface for DOCX-to-PDF conversion.
Implementations live in the infrastructure layer (GotenbergPdfConverter).
The domain layer imports ONLY this port — never a concrete adapter.

ADR-PDF-01: async bytes-in/bytes-out contract.
REQ-PDF-01: abstract async convert(docx_bytes: bytes) -> bytes.
REQ-PDF-06: raises only PdfConversionError on failure.
REQ-PDF-10: must be natively async (no asyncio.to_thread).
"""

from abc import ABC, abstractmethod

from app.domain.exceptions import PdfConversionError  # noqa: F401 — re-exported for convenience


class PdfConverter(ABC):
    """Abstract port for converting DOCX bytes to PDF bytes.

    Any concrete implementation MUST:
    - Be declared async.
    - Return the raw PDF bytes on success.
    - Raise PdfConversionError on ANY failure (HTTP errors, network errors,
      invalid input). NO other exception type may propagate to the caller.
    """

    @abstractmethod
    async def convert(self, docx_bytes: bytes) -> bytes:
        """Convert DOCX bytes to PDF bytes.

        Args:
            docx_bytes: Raw bytes of a valid DOCX file. Empty bytes MUST
                        raise PdfConversionError before any I/O is performed.

        Returns:
            Raw PDF bytes on success.

        Raises:
            PdfConversionError: On any conversion failure.
        """
        ...
