"""Unit tests for the PdfConverter port interface — T-DOMAIN-04.

Tests must FAIL (red) before pdf_converter.py is created.
"""
import inspect
import pytest


def test_pdf_converter_is_abstract() -> None:
    """PdfConverter must be an ABC with at least one abstract method (REQ-PDF-01)."""
    from abc import ABC

    from app.domain.ports.pdf_converter import PdfConverter

    assert issubclass(PdfConverter, ABC)
    # Should NOT be directly instantiable
    with pytest.raises(TypeError):
        PdfConverter()  # type: ignore[abstract]


def test_pdf_converter_has_convert_method() -> None:
    """PdfConverter must expose an abstract async convert(docx_bytes) -> bytes method."""
    from app.domain.ports.pdf_converter import PdfConverter

    assert hasattr(PdfConverter, "convert")
    method = PdfConverter.convert
    assert getattr(method, "__isabstractmethod__", False), "convert must be abstract"


def test_pdf_converter_convert_signature() -> None:
    """convert must accept self + docx_bytes: bytes and return bytes (REQ-PDF-01)."""
    from app.domain.ports.pdf_converter import PdfConverter

    sig = inspect.signature(PdfConverter.convert)
    params = list(sig.parameters.keys())
    assert "docx_bytes" in params, f"Expected 'docx_bytes' in params, got: {params}"


def test_pdf_converter_convert_is_coroutine() -> None:
    """convert must be declared async (REQ-PDF-10)."""
    import asyncio

    from app.domain.ports.pdf_converter import PdfConverter

    # Concrete subclass that implements the method so we can inspect it
    class _Concrete(PdfConverter):
        async def convert(self, docx_bytes: bytes) -> bytes:
            return b""

    assert asyncio.iscoroutinefunction(_Concrete.convert), "convert must be async"


def test_concrete_without_convert_raises_type_error() -> None:
    """A subclass that omits convert() must raise TypeError on instantiation."""
    from app.domain.ports.pdf_converter import PdfConverter

    class _Incomplete(PdfConverter):
        pass

    with pytest.raises(TypeError):
        _Incomplete()  # type: ignore[abstract]
