import asyncio
import io
import os
import tempfile

from docxtpl import DocxTemplate

from app.domain.ports.template_engine import TemplateEngine


class DocxTemplateEngine(TemplateEngine):
    """
    Template engine adapter using python-docx-template (docxtpl).

    CRITICAL DESIGN NOTES:
    - DocxTemplate CANNOT be reused after render() — internal XML is modified in-place.
      A FRESH instance must be created for every render call.
    - All operations run via asyncio.to_thread() to avoid blocking the event loop.
    - Always use autoescape=True to prevent XML injection from user-provided values.
    """

    async def extract_variables(self, file_bytes: bytes) -> list[str]:
        """Extract all Jinja2 variable names from a .docx template."""

        def _extract(data: bytes) -> list[str]:
            # Write to temp file because DocxTemplate needs a file path or file-like object
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
                tmp.write(data)
                tmp_path = tmp.name
            try:
                tpl = DocxTemplate(tmp_path)
                variables = tpl.get_undeclared_template_variables()
                return sorted(variables)
            finally:
                os.unlink(tmp_path)

        return await asyncio.to_thread(_extract, file_bytes)

    async def render(self, file_bytes: bytes, variables: dict[str, str]) -> bytes:
        """
        Render a template with the given variables.

        IMPORTANT: Creates a FRESH DocxTemplate instance every time.
        Cannot reuse — render() modifies internal XML in-place.
        """

        def _render(data: bytes, context: dict[str, str]) -> bytes:
            # Write template to temp file
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
                tmp.write(data)
                tmp_path = tmp.name
            try:
                # FRESH instance — NEVER reuse after render
                tpl = DocxTemplate(tmp_path)
                tpl.render(context, autoescape=True)

                # Save rendered document to BytesIO
                output = io.BytesIO()
                tpl.save(output)
                output.seek(0)
                return output.read()
            finally:
                os.unlink(tmp_path)

        return await asyncio.to_thread(_render, file_bytes, variables)
