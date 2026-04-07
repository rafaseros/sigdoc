import asyncio
import io
import os
import re
import tempfile

from docx import Document
from docxtpl import DocxTemplate

from app.domain.ports.template_engine import TemplateEngine


def _camel_to_snake(name: str) -> str:
    """Convert camelCase/PascalCase to snake_case."""
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


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

    async def validate(self, file_bytes: bytes) -> dict:
        """
        Validate a template file and return validation results.

        Returns a dict with:
        - valid: bool
        - variables: list[str] — extracted variable names
        - errors: list of error dicts
        - has_fixable_errors: bool
        - has_unfixable_errors: bool
        """

        def _validate_sync(data: bytes) -> dict:
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
                tmp.write(data)
                tmp_path = tmp.name

            try:
                doc = Document(tmp_path)
                errors: list[dict] = []
                all_variables: set[str] = set()

                # Collect all paragraphs: body + headers + footers
                all_paragraphs = list(doc.paragraphs)
                for section in doc.sections:
                    if section.header:
                        all_paragraphs.extend(section.header.paragraphs)
                    if section.footer:
                        all_paragraphs.extend(section.footer.paragraphs)

                for para in all_paragraphs:
                    full_text = para.text

                    # 1. No-space variables: {{var}}
                    no_space_matches = re.findall(r"\{\{(\w+)\}\}", full_text)
                    for match in no_space_matches:
                        all_variables.add(match)
                        suggested = _camel_to_snake(match.lower())
                        errors.append({
                            "type": "no_spaces",
                            "message": (
                                f"Variable sin espacios: {{{{{match}}}}}. "
                                f"Use {{{{ {suggested} }}}}"
                            ),
                            "variable": match,
                            "fixable": True,
                            "suggestion": suggested,
                        })

                    # 2. Properly formatted variables {{ var }}
                    proper_matches = re.findall(r"\{\{\s+(\w+)\s+\}\}", full_text)
                    for match in proper_matches:
                        all_variables.add(match)

                        # Check uppercase / camelCase
                        if match != match.lower() or re.search(r"[A-Z]", match):
                            suggested = _camel_to_snake(match.lower())
                            errors.append({
                                "type": "uppercase",
                                "message": (
                                    f"Variable con mayúsculas: {{{{ {match} }}}}. "
                                    f"Use {{{{ {suggested} }}}}"
                                ),
                                "variable": match,
                                "fixable": True,
                                "suggestion": suggested,
                            })

                        # Check special characters (accents, ñ, etc.)
                        if re.search(r"[^\x00-\x7F]", match):
                            errors.append({
                                "type": "special_chars",
                                "message": (
                                    f"Variable con caracteres especiales: {{{{ {match} }}}}. "
                                    "Use solo letras ASCII, números y guiones bajos."
                                ),
                                "variable": match,
                                "fixable": False,
                                "suggestion": None,
                            })

                    # Also check special chars in no-space variables
                    for match in no_space_matches:
                        if re.search(r"[^\x00-\x7F]", match):
                            errors.append({
                                "type": "special_chars",
                                "message": (
                                    f"Variable con caracteres especiales: {{{{{match}}}}}. "
                                    "Use solo letras ASCII, números y guiones bajos."
                                ),
                                "variable": match,
                                "fixable": False,
                                "suggestion": None,
                            })

                    # 3. Split formatting — variable across multiple runs
                    runs_text = [run.text for run in para.runs]
                    combined = "".join(runs_text)
                    combined_vars = re.findall(r"\{\{.*?\}\}", combined)
                    for cv in combined_vars:
                        found_in_single_run = any(cv in rt for rt in runs_text)
                        if not found_in_single_run:
                            var_name = re.search(r"\{\{\s*(\w+)\s*\}\}", cv)
                            name = var_name.group(1) if var_name else cv
                            errors.append({
                                "type": "split_format",
                                "message": (
                                    f"Variable con formato dividido: {cv}. "
                                    "El formato (negrita, cursiva, etc.) debe ser uniforme "
                                    "en toda la variable. Seleccione todo el marcador en Word "
                                    "y aplique el formato de manera uniforme."
                                ),
                                "variable": name,
                                "fixable": False,
                                "suggestion": None,
                            })

                    # 4. Unclosed braces
                    if "{{" in full_text and "}}" not in full_text:
                        errors.append({
                            "type": "invalid_syntax",
                            "message": (
                                f'Llaves sin cerrar detectadas en: "{full_text[:80]}..."'
                            ),
                            "variable": None,
                            "fixable": False,
                            "suggestion": None,
                        })

                # 5. No variables at all
                if not all_variables and not errors:
                    errors.append({
                        "type": "no_variables",
                        "message": (
                            "No se encontraron variables en el documento. "
                            "Asegúrese de usar la sintaxis {{ nombre_variable }} con espacios."
                        ),
                        "variable": None,
                        "fixable": False,
                        "suggestion": None,
                    })

                # Deduplicate by (type, variable)
                seen: set[tuple] = set()
                unique_errors: list[dict] = []
                for e in errors:
                    key = (e["type"], e["variable"])
                    if key not in seen:
                        seen.add(key)
                        unique_errors.append(e)

                has_fixable = any(e["fixable"] for e in unique_errors)
                has_unfixable = any(not e["fixable"] for e in unique_errors)

                return {
                    "valid": len(unique_errors) == 0,
                    "variables": sorted(all_variables),
                    "errors": unique_errors,
                    "has_fixable_errors": has_fixable,
                    "has_unfixable_errors": has_unfixable,
                }
            finally:
                os.unlink(tmp_path)

        return await asyncio.to_thread(_validate_sync, file_bytes)

    async def auto_fix(self, file_bytes: bytes) -> bytes:
        """
        Auto-fix fixable issues in a template file.

        Fixes: no-space variables, uppercase, camelCase -> snake_case.
        Does NOT fix: special chars, split formatting.
        Returns the corrected file bytes.
        """

        def _auto_fix_sync(data: bytes) -> bytes:
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
                tmp.write(data)
                tmp_path = tmp.name

            try:
                doc = Document(tmp_path)

                all_paragraphs = list(doc.paragraphs)
                for section in doc.sections:
                    if section.header:
                        all_paragraphs.extend(section.header.paragraphs)
                    if section.footer:
                        all_paragraphs.extend(section.footer.paragraphs)

                for para in all_paragraphs:
                    for run in para.runs:
                        original = run.text
                        fixed = original

                        # Fix {{var}} -> {{ snake_case }}
                        fixed = re.sub(
                            r"\{\{(\w+)\}\}",
                            lambda m: "{{ "
                            + _camel_to_snake(m.group(1).lower())
                            + " }}",
                            fixed,
                        )

                        # Fix {{ Var }} or {{ camelCase }} -> {{ snake_case }}
                        fixed = re.sub(
                            r"\{\{\s+(\w+)\s+\}\}",
                            lambda m: "{{ "
                            + _camel_to_snake(m.group(1).lower())
                            + " }}",
                            fixed,
                        )

                        if fixed != original:
                            run.text = fixed

                output = io.BytesIO()
                doc.save(output)
                output.seek(0)
                return output.read()
            finally:
                os.unlink(tmp_path)

        return await asyncio.to_thread(_auto_fix_sync, file_bytes)
