"""Unit tests for GotenbergPdfConverter adapter — T-INFRA-06.

Must FAIL (red) before the adapter is implemented.

REQs: REQ-PDF-02, REQ-PDF-08, REQ-PDF-09
Scenarios: SCEN-PDF-01..05

Uses `respx` to mock httpx — no real HTTP calls are made.
"""
import pytest
import respx
import httpx

from app.domain.exceptions import PdfConversionError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

GOTENBERG_URL = "http://gotenberg:3000"
CONVERT_URL = f"{GOTENBERG_URL}/forms/libreoffice/convert"
FAKE_DOCX = b"PK\x03\x04fake-docx-bytes"  # minimal non-empty bytes
FAKE_PDF = b"%PDF-1.4 fake-pdf-bytes"


def _make_converter():
    """Construct a GotenbergPdfConverter with the test Gotenberg URL."""
    from app.infrastructure.pdf.gotenberg_pdf_converter import GotenbergPdfConverter

    return GotenbergPdfConverter(gotenberg_url=GOTENBERG_URL, timeout=5)


# ---------------------------------------------------------------------------
# SCEN-PDF-01: Happy path — 2xx response returns PDF bytes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_convert_success_returns_pdf_bytes() -> None:
    """SCEN-PDF-01: POST to Gotenberg returns 200 with PDF bytes."""
    respx.post(CONVERT_URL).mock(
        return_value=httpx.Response(200, content=FAKE_PDF)
    )
    converter = _make_converter()
    result = await converter.convert(FAKE_DOCX)
    assert result == FAKE_PDF


@pytest.mark.asyncio
@respx.mock
async def test_convert_success_sends_multipart_with_correct_field() -> None:
    """SCEN-PDF-01: POST must include multipart `files` field with DOCX content."""
    route = respx.post(CONVERT_URL).mock(
        return_value=httpx.Response(200, content=FAKE_PDF)
    )
    converter = _make_converter()
    await converter.convert(FAKE_DOCX)

    request = route.calls.last.request
    assert request is not None
    content_type = request.headers.get("content-type", "")
    assert "multipart/form-data" in content_type


# ---------------------------------------------------------------------------
# SCEN-PDF-02: 5xx response → PdfConversionError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_convert_5xx_raises_pdf_conversion_error() -> None:
    """SCEN-PDF-02: Non-2xx response raises PdfConversionError with status ref."""
    respx.post(CONVERT_URL).mock(
        return_value=httpx.Response(500, content=b"Internal Server Error")
    )
    converter = _make_converter()
    with pytest.raises(PdfConversionError) as exc_info:
        await converter.convert(FAKE_DOCX)
    assert "500" in str(exc_info.value)


@pytest.mark.asyncio
@respx.mock
async def test_convert_4xx_raises_pdf_conversion_error() -> None:
    """Non-2xx (4xx) response also raises PdfConversionError."""
    respx.post(CONVERT_URL).mock(
        return_value=httpx.Response(422, content=b"Unprocessable")
    )
    converter = _make_converter()
    with pytest.raises(PdfConversionError):
        await converter.convert(FAKE_DOCX)


# ---------------------------------------------------------------------------
# SCEN-PDF-03: Connection refused → PdfConversionError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_convert_connection_refused_raises_pdf_conversion_error() -> None:
    """SCEN-PDF-03: httpx.ConnectError wraps as PdfConversionError."""
    respx.post(CONVERT_URL).mock(side_effect=httpx.ConnectError("Connection refused"))
    converter = _make_converter()
    with pytest.raises(PdfConversionError) as exc_info:
        await converter.convert(FAKE_DOCX)
    assert "connect" in str(exc_info.value).lower() or "connection" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# SCEN-PDF-04: Timeout → PdfConversionError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_convert_timeout_raises_pdf_conversion_error() -> None:
    """SCEN-PDF-04: httpx.TimeoutException wraps as PdfConversionError."""
    respx.post(CONVERT_URL).mock(side_effect=httpx.TimeoutException("Timeout"))
    converter = _make_converter()
    with pytest.raises(PdfConversionError) as exc_info:
        await converter.convert(FAKE_DOCX)
    assert "timeout" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# SCEN-PDF-05: Empty input → PdfConversionError BEFORE HTTP call
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_convert_empty_bytes_raises_before_http_call() -> None:
    """SCEN-PDF-05: Empty docx_bytes raises PdfConversionError before any HTTP call."""
    route = respx.post(CONVERT_URL).mock(
        return_value=httpx.Response(200, content=FAKE_PDF)
    )
    converter = _make_converter()
    with pytest.raises(PdfConversionError) as exc_info:
        await converter.convert(b"")
    # Must NOT have made an HTTP call
    assert route.called is False
    assert "empty" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# REQ-PDF-09: Logging — success logs INFO, failure logs ERROR
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_convert_success_logs_info(caplog) -> None:
    """REQ-PDF-09: Successful conversion logs an INFO message with duration."""
    import logging

    respx.post(CONVERT_URL).mock(
        return_value=httpx.Response(200, content=FAKE_PDF)
    )
    converter = _make_converter()
    with caplog.at_level(logging.INFO, logger="app.infrastructure.pdf.gotenberg_pdf_converter"):
        await converter.convert(FAKE_DOCX)

    assert any("ms" in record.message.lower() or "success" in record.message.lower() or "pdf" in record.message.lower()
                for record in caplog.records), \
        f"Expected INFO log with duration or success indicator; got: {[r.message for r in caplog.records]}"


@pytest.mark.asyncio
@respx.mock
async def test_convert_5xx_logs_error(caplog) -> None:
    """REQ-PDF-09: Failed conversion logs an ERROR message."""
    import logging

    respx.post(CONVERT_URL).mock(
        return_value=httpx.Response(500, content=b"err")
    )
    converter = _make_converter()
    with caplog.at_level(logging.ERROR, logger="app.infrastructure.pdf.gotenberg_pdf_converter"):
        with pytest.raises(PdfConversionError):
            await converter.convert(FAKE_DOCX)

    assert any(record.levelname == "ERROR" for record in caplog.records), \
        f"Expected ERROR log; got: {[r.levelname + ': ' + r.message for r in caplog.records]}"
