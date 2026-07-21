import re

from app.domain.exceptions import (
    InvalidVariableMappingError,
    MappingTextNotFoundError,
)
from app.domain.ports.template_engine import TemplateEngine

_VARIABLE_NAME_RE = re.compile(r"^[a-z_][a-z0-9_]*$")
_PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


class FakeTemplateEngine(TemplateEngine):
    """In-memory implementation of TemplateEngine for testing.

    Documents are modeled as plain UTF-8 text bytes:
    - apply_variable_mappings does string-level replacement of literals with
      {{ placeholder }} markers (same validation rules as the real engine).
    - extract_variables first scans the bytes for {{ ... }} markers; when the
      bytes decode and contain markers, those names are returned (in order of
      first appearance). Otherwise it falls back to `variables_to_return`,
      preserving the historical configurable behavior.

    Configurable via constructor arguments:
    - variables_to_return: list of variable name strings returned by
      extract_variables when the bytes contain no {{ ... }} markers
    - render_result: bytes returned by render()
    - should_fail: if True, render() raises RuntimeError
    """

    def __init__(
        self,
        variables_to_return: list[str] | None = None,
        render_result: bytes = b"rendered-document",
        should_fail: bool = False,
        structure_to_return: dict | None = None,
    ) -> None:
        self.variables_to_return: list[str] = variables_to_return or []
        self.render_result: bytes = render_result
        self.should_fail: bool = should_fail
        self.structure_to_return: dict = structure_to_return or {
            "headers": [],
            "body": [],
            "footers": [],
        }

    async def extract_variables(self, file_bytes: bytes) -> list[dict]:
        """Scan the bytes for {{ ... }} markers; fall back to variables_to_return."""
        try:
            text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text = ""

        scanned = list(dict.fromkeys(_PLACEHOLDER_RE.findall(text)))
        names = scanned if scanned else self.variables_to_return
        return [
            {"name": name, "contexts": [f"context for {name}"]}
            for name in names
        ]

    async def render(self, file_bytes: bytes, variables: dict[str, str]) -> bytes:
        if self.should_fail:
            raise RuntimeError("FakeTemplateEngine: render failed (should_fail=True)")
        return self.render_result

    async def validate(self, file_bytes: bytes) -> dict:
        return {"valid": True, "errors": [], "warnings": []}

    async def auto_fix(self, file_bytes: bytes) -> bytes:
        return file_bytes

    async def apply_variable_mappings(
        self, file_bytes: bytes, mappings: list[dict]
    ) -> bytes:
        """String-level rewrite mirroring the real engine's contract."""
        if not mappings:
            raise InvalidVariableMappingError(
                "Debe indicar al menos un mapeo de texto a variable"
            )

        seen_texts: set[str] = set()
        for mapping in mappings:
            text = mapping.get("text")
            variable = mapping.get("variable")
            if not isinstance(text, str) or not text.strip():
                raise InvalidVariableMappingError(
                    "Cada mapeo debe incluir un texto no vacío"
                )
            if not isinstance(variable, str) or not _VARIABLE_NAME_RE.match(variable):
                raise InvalidVariableMappingError(
                    f"Nombre de variable inválido: '{variable}'. "
                    "Use minúsculas snake_case (ej: nombre_cliente)"
                )
            if text in seen_texts:
                raise InvalidVariableMappingError(
                    f"Texto duplicado en los mapeos: '{text}'"
                )
            seen_texts.add(text)

        content = file_bytes.decode("utf-8", errors="replace")

        found: set[str] = set()
        # Longest-text-first so contained texts are handled after containers
        for mapping in sorted(mappings, key=lambda m: len(m["text"]), reverse=True):
            if mapping["text"] in content:
                found.add(mapping["text"])
                content = content.replace(
                    mapping["text"], "{{ " + mapping["variable"] + " }}"
                )

        missing = [m["text"] for m in mappings if m["text"] not in found]
        if missing:
            raise MappingTextNotFoundError(missing)

        return content.encode("utf-8")

    async def extract_structure(self, file_bytes: bytes) -> dict:
        return self.structure_to_return
