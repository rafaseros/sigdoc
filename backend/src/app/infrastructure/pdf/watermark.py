"""Server-side preview watermark.

Stamps a diagonal, semi-transparent watermark on EVERY page of a PDF so a
preview render can never be mistaken for (or used as) a final document.

apply_watermark() is a pure, synchronous, CPU-bound function — callers that
run in an async context (e.g. DocumentService.preview()) MUST offload it via
asyncio.to_thread() to avoid blocking the event loop.
"""
from __future__ import annotations

import io
import math

from pypdf import PdfReader, PdfWriter
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

# Font used for the watermark text — must be one of the 14 standard PDF
# fonts so no font embedding is required.
_FONT_NAME = "Helvetica-Bold"

# Semi-transparent light neutral gray-blue, chosen to be legible over any
# document content without obscuring it.
_FILL_COLOR_RGB = (0.55, 0.60, 0.68)
_FILL_ALPHA = 0.15

# Fallback fill color used only if the reportlab canvas backend does not
# support alpha transparency (setFillAlpha unavailable).
_FALLBACK_FILL_COLOR_RGB = (0.75, 0.75, 0.75)

# Font size is scaled to the page diagonal so the watermark spans most of
# the page without overflowing it, clamped to this sane range.
_MIN_FONT_SIZE = 12.0
_MAX_FONT_SIZE = 96.0

# Fraction of the page diagonal the watermark text should span.
_TARGET_DIAGONAL_FRACTION = 0.8

# Reference font size used to measure string width before scaling — any
# positive value works since stringWidth scales linearly with font size.
_REFERENCE_FONT_SIZE = 100.0


def apply_watermark(pdf_bytes: bytes, text: str) -> bytes:
    """Return a copy of *pdf_bytes* with *text* watermarked on every page.

    The watermark is drawn diagonally (45 degrees), centered on each page,
    semi-transparent, and sized relative to that page's own diagonal — so
    pages of different sizes/orientations within the same document each get
    a correctly proportioned watermark.

    Args:
        pdf_bytes: Raw PDF bytes to watermark.
        text: Watermark text to stamp on every page.

    Returns:
        New PDF bytes, same page count as the input, with the watermark
        merged onto every page.

    Raises:
        ValueError: If pdf_bytes is empty, unreadable, or has no pages.

    Note:
        Input encrypted only with an owner password is auto-decrypted by
        pypdf and the output is written UNENCRYPTED — print/copy
        restrictions are dropped. Irrelevant for Gotenberg output (never
        encrypted), but a real caveat if this module is reused on
        user-supplied PDFs.
    """
    if not pdf_bytes:
        raise ValueError("Cannot watermark empty PDF bytes")

    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        page_count = len(reader.pages)
    except Exception as exc:
        raise ValueError(f"Cannot watermark unreadable PDF: {exc}") from exc

    if page_count == 0:
        raise ValueError("Cannot watermark a PDF with no pages")

    # Clone into the writer FIRST so pages are attached to it before
    # merge_page() runs — merging onto a page that isn't attached to a
    # writer is deprecated in pypdf (removal planned in pypdf 7.0).
    writer = PdfWriter(clone_from=reader)

    for page in writer.pages:
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)

        overlay_page = _build_overlay_page(width, height, text)
        # The overlay is built in a (0,0)-origin coordinate space; translate
        # it by the page's mediabox origin so the watermark stays centered on
        # pages whose mediabox does not start at (0,0).
        page.merge_transformed_page(
            overlay_page,
            (
                1,
                0,
                0,
                1,
                float(page.mediabox.left),
                float(page.mediabox.bottom),
            ),
        )

    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def _build_overlay_page(width: float, height: float, text: str):
    """Build a single-page pypdf page containing the watermark, sized to
    match (width, height) exactly so it can be merged onto the target page.
    """
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(width, height))

    font_size = _font_size_for_page(width, height, text)

    c.saveState()
    c.translate(width / 2, height / 2)
    c.rotate(45)
    c.setFont(_FONT_NAME, font_size)
    try:
        c.setFillAlpha(_FILL_ALPHA)
        c.setFillColorRGB(*_FILL_COLOR_RGB)
    except AttributeError:
        # Some reportlab canvas backends don't support fill alpha — fall
        # back silently to a plain light gray so the watermark still
        # renders, just without transparency.
        c.setFillColorRGB(*_FALLBACK_FILL_COLOR_RGB)
    c.drawCentredString(0, 0, text)
    c.restoreState()
    c.showPage()
    c.save()
    buffer.seek(0)

    overlay_reader = PdfReader(buffer)
    return overlay_reader.pages[0]


def _font_size_for_page(width: float, height: float, text: str) -> float:
    """Compute a font size so *text* spans most of the page diagonal
    without overflowing it, clamped to a sane range.
    """
    diagonal = math.hypot(width, height)
    target_text_width = diagonal * _TARGET_DIAGONAL_FRACTION

    reference_width = stringWidth(text, _FONT_NAME, _REFERENCE_FONT_SIZE)
    if reference_width <= 0:
        return _MIN_FONT_SIZE

    font_size = (target_text_width / reference_width) * _REFERENCE_FONT_SIZE
    return max(_MIN_FONT_SIZE, min(_MAX_FONT_SIZE, font_size))
