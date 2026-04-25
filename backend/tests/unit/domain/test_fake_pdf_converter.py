"""Contract tests for FakePdfConverter — T-DOMAIN-05.

These tests must FAIL (red) before FakePdfConverter is implemented (T-DOMAIN-06).
Covers: REQ-PDF-07, SCEN-PDF-06.
"""
import pytest

from app.domain.exceptions import PdfConversionError


@pytest.mark.asyncio
async def test_fake_pdf_converter_returns_configured_bytes() -> None:
    """Success mode: convert() returns convert_result bytes (REQ-PDF-07)."""
    from tests.fakes.fake_pdf_converter import FakePdfConverter

    fake = FakePdfConverter(convert_result=b"fake-pdf-content")
    result = await fake.convert(b"some-docx-bytes")
    assert result == b"fake-pdf-content"


@pytest.mark.asyncio
async def test_fake_pdf_converter_default_convert_result() -> None:
    """Default convert_result must be non-empty bytes when not specified."""
    from tests.fakes.fake_pdf_converter import FakePdfConverter

    fake = FakePdfConverter()
    result = await fake.convert(b"some-docx-bytes")
    assert isinstance(result, bytes)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_fake_pdf_converter_set_failure_causes_next_call_to_raise() -> None:
    """set_failure(exc) causes next convert() to raise that exception (SCEN-PDF-06)."""
    from tests.fakes.fake_pdf_converter import FakePdfConverter

    fake = FakePdfConverter(convert_result=b"ok")
    exc = PdfConversionError("forced failure")
    fake.set_failure(exc)

    with pytest.raises(PdfConversionError, match="forced failure"):
        await fake.convert(b"some-docx-bytes")


@pytest.mark.asyncio
async def test_fake_pdf_converter_failure_cleared_after_single_use() -> None:
    """Failure state is single-use — subsequent call succeeds (SCEN-PDF-06)."""
    from tests.fakes.fake_pdf_converter import FakePdfConverter

    fake = FakePdfConverter(convert_result=b"recovered")
    fake.set_failure(PdfConversionError("one-time failure"))

    # First call: raises
    with pytest.raises(PdfConversionError):
        await fake.convert(b"bytes")

    # Second call: succeeds — failure state was cleared
    result = await fake.convert(b"bytes")
    assert result == b"recovered"


@pytest.mark.asyncio
async def test_fake_pdf_converter_implements_pdf_converter_port() -> None:
    """FakePdfConverter must be a concrete implementation of PdfConverter."""
    from app.domain.ports.pdf_converter import PdfConverter
    from tests.fakes.fake_pdf_converter import FakePdfConverter

    fake = FakePdfConverter()
    assert isinstance(fake, PdfConverter)
