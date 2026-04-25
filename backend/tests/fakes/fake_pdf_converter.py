"""FakePdfConverter — in-memory test double for PdfConverter.

Implements PdfConverter with configurable success bytes and single-use
failure injection via set_failure(). Used by all service-layer tests that
need PDF conversion without a real Gotenberg instance.

REQ-PDF-07: supports convert_result and set_failure(exc) API.
SCEN-PDF-06: failure state is cleared after a single use.
"""

from app.domain.exceptions import PdfConversionError
from app.domain.ports.pdf_converter import PdfConverter


class FakePdfConverter(PdfConverter):
    """In-memory implementation of PdfConverter for testing.

    Attributes:
        convert_result: Bytes returned by convert() on success.
        _pending_failure: If set, the next convert() call raises this exception
                          and then clears the state (single-use).
        call_count: Number of times convert() was called (useful for assertions).
    """

    def __init__(self, convert_result: bytes = b"fake-pdf-bytes") -> None:
        self.convert_result: bytes = convert_result
        self._pending_failure: PdfConversionError | None = None
        self.call_count: int = 0

    def set_failure(self, exc: PdfConversionError) -> None:
        """Configure the next convert() call to raise *exc*.

        The failure is single-use: after raising once, the fake returns to
        success mode. This matches the contract from SCEN-PDF-06.
        """
        self._pending_failure = exc

    async def convert(self, docx_bytes: bytes) -> bytes:
        """Return convert_result bytes, or raise the pending failure if set.

        Args:
            docx_bytes: DOCX content (not validated by the fake — tests
                        may pass any bytes including empty bytes).

        Returns:
            convert_result bytes on success.

        Raises:
            PdfConversionError: If set_failure() was called before this call.
        """
        self.call_count += 1

        if self._pending_failure is not None:
            exc = self._pending_failure
            self._pending_failure = None  # single-use: clear immediately
            raise exc

        return self.convert_result
