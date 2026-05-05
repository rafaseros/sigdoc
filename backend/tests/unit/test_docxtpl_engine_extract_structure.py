"""
Unit tests for DocxTemplateEngine.extract_structure() — full document structure
preview used by the generation UI.

Each paragraph is returned as a node with `kind`, `level`, and a list of `spans`
where each span is either plain text or a {{ variable }} placeholder. Headers,
body and footers are returned as three separate lists.
"""

import io

import pytest
from docx import Document

from app.infrastructure.templating.docxtpl_engine import DocxTemplateEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _doc_bytes(build) -> bytes:
    """Run `build(doc)` on a fresh Document and return the bytes."""
    doc = Document()
    build(doc)
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.read()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestExtractStructureBody:
    """Body section: paragraphs, headings, placeholders, edge cases."""

    async def test_plain_paragraph_returns_single_text_span(self):
        engine = DocxTemplateEngine()
        raw = _doc_bytes(lambda d: d.add_paragraph("Hola mundo"))

        result = await engine.extract_structure(raw)

        assert result["body"] == [
            {"kind": "paragraph", "level": 0, "spans": [{"text": "Hola mundo", "variable": None}]}
        ]
        assert result["headers"] == []
        assert result["footers"] == []

    async def test_paragraph_with_placeholder_splits_into_spans(self):
        engine = DocxTemplateEngine()
        raw = _doc_bytes(
            lambda d: d.add_paragraph("Estimado {{ nombre }}, gracias.")
        )

        result = await engine.extract_structure(raw)

        body = result["body"]
        assert len(body) == 1
        assert body[0]["kind"] == "paragraph"
        assert body[0]["spans"] == [
            {"text": "Estimado ", "variable": None},
            {"text": "{{ nombre }}", "variable": "nombre"},
            {"text": ", gracias.", "variable": None},
        ]

    async def test_paragraph_starting_with_placeholder_no_leading_text_span(self):
        """When the placeholder is at position 0, no empty text span is emitted."""
        engine = DocxTemplateEngine()
        raw = _doc_bytes(lambda d: d.add_paragraph("{{ nombre }} firma."))

        result = await engine.extract_structure(raw)

        spans = result["body"][0]["spans"]
        assert spans[0] == {"text": "{{ nombre }}", "variable": "nombre"}
        assert spans[1] == {"text": " firma.", "variable": None}
        assert len(spans) == 2

    async def test_paragraph_ending_with_placeholder_no_trailing_text_span(self):
        engine = DocxTemplateEngine()
        raw = _doc_bytes(lambda d: d.add_paragraph("Firma: {{ nombre }}"))

        result = await engine.extract_structure(raw)

        spans = result["body"][0]["spans"]
        assert spans == [
            {"text": "Firma: ", "variable": None},
            {"text": "{{ nombre }}", "variable": "nombre"},
        ]

    async def test_multiple_placeholders_same_paragraph(self):
        engine = DocxTemplateEngine()
        raw = _doc_bytes(
            lambda d: d.add_paragraph("Entre {{ empresa }} y {{ contratado }}.")
        )

        result = await engine.extract_structure(raw)

        spans = result["body"][0]["spans"]
        variables = [s["variable"] for s in spans if s["variable"]]
        assert variables == ["empresa", "contratado"]

    async def test_empty_paragraphs_are_skipped(self):
        """Whitespace-only paragraphs do not become nodes — they would just clutter the preview."""
        engine = DocxTemplateEngine()

        def build(d):
            d.add_paragraph("Primero")
            d.add_paragraph("")
            d.add_paragraph("   ")
            d.add_paragraph("Tercero")

        raw = _doc_bytes(build)
        result = await engine.extract_structure(raw)

        texts = [n["spans"][0]["text"] for n in result["body"]]
        assert texts == ["Primero", "Tercero"]

    async def test_heading_detected_with_level(self):
        engine = DocxTemplateEngine()

        def build(d):
            d.add_heading("Título principal", level=1)
            d.add_heading("Sección", level=2)
            d.add_paragraph("Contenido normal")

        raw = _doc_bytes(build)
        result = await engine.extract_structure(raw)

        body = result["body"]
        assert body[0]["kind"] == "heading"
        assert body[0]["level"] == 1
        assert body[1]["kind"] == "heading"
        assert body[1]["level"] == 2
        assert body[2]["kind"] == "paragraph"
        assert body[2]["level"] == 0


class TestExtractStructureHeadersFooters:
    """Headers and footers must be returned in their own lists, not in body."""

    async def test_header_paragraphs_returned_separately(self):
        engine = DocxTemplateEngine()

        def build(d):
            section = d.sections[0]
            section.header.paragraphs[0].text = "Encabezado de página"
            d.add_paragraph("Cuerpo del contrato")

        raw = _doc_bytes(build)
        result = await engine.extract_structure(raw)

        assert len(result["headers"]) == 1
        assert result["headers"][0]["spans"][0]["text"] == "Encabezado de página"
        assert len(result["body"]) == 1
        assert result["body"][0]["spans"][0]["text"] == "Cuerpo del contrato"

    async def test_footer_paragraphs_returned_separately(self):
        engine = DocxTemplateEngine()

        def build(d):
            section = d.sections[0]
            section.footer.paragraphs[0].text = "Página {{ page }}"
            d.add_paragraph("Cuerpo")

        raw = _doc_bytes(build)
        result = await engine.extract_structure(raw)

        assert len(result["footers"]) == 1
        assert result["footers"][0]["spans"] == [
            {"text": "Página ", "variable": None},
            {"text": "{{ page }}", "variable": "page"},
        ]

    async def test_placeholders_in_headers_are_parsed(self):
        engine = DocxTemplateEngine()

        def build(d):
            d.sections[0].header.paragraphs[0].text = (
                "Contrato {{ numero_contrato }} — {{ nombre_empresa }}"
            )
            d.add_paragraph("Cuerpo")

        raw = _doc_bytes(build)
        result = await engine.extract_structure(raw)

        header_vars = [
            s["variable"] for s in result["headers"][0]["spans"] if s["variable"]
        ]
        assert header_vars == ["numero_contrato", "nombre_empresa"]


class TestExtractStructureMisc:
    async def test_returns_three_keys_always(self):
        """Even an empty .docx should return all three keys with empty lists."""
        engine = DocxTemplateEngine()
        raw = _doc_bytes(lambda d: None)

        result = await engine.extract_structure(raw)

        assert result == {"headers": [], "body": [], "footers": []}

    async def test_invalid_variable_name_with_dash_is_not_a_placeholder(self):
        """Variable names allow only [a-zA-Z_][a-zA-Z0-9_]*. A dash makes it plain text."""
        engine = DocxTemplateEngine()
        raw = _doc_bytes(lambda d: d.add_paragraph("Texto {{ no-valid }} fin"))

        result = await engine.extract_structure(raw)

        # Whole paragraph should be a single text span — the regex shouldn't match.
        spans = result["body"][0]["spans"]
        assert len(spans) == 1
        assert spans[0]["variable"] is None
