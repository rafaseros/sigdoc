"""Unit tests for the server-side preview watermark.

Covers app.infrastructure.pdf.watermark.apply_watermark(): a pure,
synchronous, CPU-bound function that stamps a diagonal semi-transparent
watermark on every page of a PDF, so a preview render can never be mistaken
for (or used as) a final document.

Strict TDD order: this test file is written first (RED), then
apply_watermark() is implemented (GREEN).
"""
from __future__ import annotations

import io

import pytest
from pypdf import PdfReader
from reportlab.lib.pagesizes import A4, landscape, letter
from reportlab.pdfgen import canvas

from app.infrastructure.pdf.watermark import apply_watermark

WATERMARK_TEXT = "VISTA PREVIA — SigDoc"


def _build_two_page_pdf() -> bytes:
    """Build a small real 2-page PDF with different page sizes/orientations.

    Page 1: A4 portrait, body text "Body page one".
    Page 2: US Letter landscape, body text "Body page two".
    """
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    c.setFont("Helvetica", 14)
    c.drawString(72, A4[1] - 100, "Body page one")
    c.showPage()

    landscape_letter = landscape(letter)
    c.setPageSize(landscape_letter)
    c.setFont("Helvetica", 14)
    c.drawString(72, landscape_letter[1] - 100, "Body page two")
    c.showPage()

    c.save()
    buffer.seek(0)
    return buffer.read()


class TestApplyWatermarkHappyPath:
    def test_returns_valid_pdf_with_same_page_count(self):
        original_bytes = _build_two_page_pdf()
        original_page_count = len(PdfReader(io.BytesIO(original_bytes)).pages)

        watermarked_bytes = apply_watermark(original_bytes, WATERMARK_TEXT)

        reader = PdfReader(io.BytesIO(watermarked_bytes))
        assert len(reader.pages) == original_page_count
        assert len(reader.pages) == 2

    def test_every_page_contains_body_text_and_watermark_text(self):
        pdf_bytes = _build_two_page_pdf()

        watermarked_bytes = apply_watermark(pdf_bytes, WATERMARK_TEXT)

        reader = PdfReader(io.BytesIO(watermarked_bytes))
        page_one_text = reader.pages[0].extract_text()
        page_two_text = reader.pages[1].extract_text()

        assert "Body page one" in page_one_text
        assert WATERMARK_TEXT in page_one_text

        assert "Body page two" in page_two_text
        assert WATERMARK_TEXT in page_two_text


class TestApplyWatermarkOffsetMediabox:
    def test_offset_mediabox_page_keeps_watermark_centered_in_page_space(self):
        """A mediabox whose origin is not (0,0) is legal PDF. The overlay is
        built in a (0,0)-origin space and must be translated by the mediabox
        origin on merge — otherwise the watermark lands offset (or entirely
        outside the visible area) while text extraction still reports it."""
        pdf_bytes = _build_two_page_pdf()

        reader = PdfReader(io.BytesIO(pdf_bytes))
        page = reader.pages[0]
        offset_x, offset_y = 200.0, 300.0
        original_width = float(page.mediabox.width)
        original_height = float(page.mediabox.height)
        from pypdf import PdfWriter
        from pypdf.generic import RectangleObject

        page.mediabox = RectangleObject(
            (
                offset_x,
                offset_y,
                offset_x + original_width,
                offset_y + original_height,
            )
        )

        writer = PdfWriter()
        writer.add_page(page)
        shifted = io.BytesIO()
        writer.write(shifted)

        watermarked = apply_watermark(shifted.getvalue(), WATERMARK_TEXT)

        out = PdfReader(io.BytesIO(watermarked))
        assert len(out.pages) == 1
        out_page = out.pages[0]
        assert WATERMARK_TEXT in out_page.extract_text()
        # The watermark glyphs must sit inside the shifted mediabox: extract
        # positioned text and check every watermark fragment's x/y lands
        # within the visible box (extraction alone cannot catch off-page
        # placement — coordinates can).
        boxes: list[tuple[float, float]] = []

        def visitor(text, cm, tm, font_dict, font_size):
            if not (text.strip() and text.strip() in WATERMARK_TEXT):
                return
            # Device-space position = text matrix composed with the canvas
            # matrix (the merge translation lives in cm, not tm).
            x = cm[0] * tm[4] + cm[2] * tm[5] + cm[4]
            y = cm[1] * tm[4] + cm[3] * tm[5] + cm[5]
            boxes.append((x, y))

        out_page.extract_text(visitor_text=visitor)
        assert boxes, "watermark text fragments must be extractable"
        left = float(out_page.mediabox.left)
        bottom = float(out_page.mediabox.bottom)
        right = float(out_page.mediabox.right)
        top = float(out_page.mediabox.top)
        for x, y in boxes:
            assert left <= x <= right, f"watermark x={x} outside [{left},{right}]"
            assert bottom <= y <= top, f"watermark y={y} outside [{bottom},{top}]"


class TestApplyWatermarkErrorHandling:
    def test_empty_bytes_raises_value_error(self):
        with pytest.raises(ValueError):
            apply_watermark(b"", WATERMARK_TEXT)

    def test_garbage_bytes_raises_value_error(self):
        with pytest.raises(ValueError):
            apply_watermark(b"this is not a pdf at all", WATERMARK_TEXT)


class TestApplyWatermarkIdempotenceSanity:
    def test_watermarking_twice_still_yields_valid_pdf_same_page_count(self):
        """No requirement to dedupe overlapping watermarks — just must not
        corrupt the document when applied more than once."""
        pdf_bytes = _build_two_page_pdf()

        once = apply_watermark(pdf_bytes, WATERMARK_TEXT)
        twice = apply_watermark(once, WATERMARK_TEXT)

        reader = PdfReader(io.BytesIO(twice))
        assert len(reader.pages) == 2
