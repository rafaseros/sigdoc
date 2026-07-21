from abc import ABC, abstractmethod


class TemplateEngine(ABC):
    @abstractmethod
    async def extract_variables(self, file_bytes: bytes) -> list[dict]:
        """
        Extract variable names and their surrounding paragraph context from a template file.

        Returns a list of dicts:
        [{"name": "variable_name", "contexts": ["paragraph text where it appears", ...]}, ...]
        """
        ...

    @abstractmethod
    async def render(self, file_bytes: bytes, variables: dict[str, str]) -> bytes:
        """Render a template with the given variables. Returns the rendered document bytes."""
        ...

    @abstractmethod
    async def validate(self, file_bytes: bytes) -> dict:
        """Validate a template file and return validation results."""
        ...

    @abstractmethod
    async def auto_fix(self, file_bytes: bytes) -> bytes:
        """Auto-fix fixable issues in a template file. Returns the corrected file bytes."""
        ...

    @abstractmethod
    async def apply_variable_mappings(
        self, file_bytes: bytes, mappings: list[dict]
    ) -> bytes:
        """
        Rewrite an example document by replacing literal text spans with
        ``{{ placeholder }}`` markers, preserving Word formatting.

        Each mapping item has the shape ``{"text": str, "variable": str}``.
        Replacement is case-sensitive exact match, applied longest-text-first
        (so a text containing another mapping's text is handled before the
        shorter one), across body paragraphs, table cells, headers, and
        footers. All occurrences of each text are replaced. The same variable
        name MAY be used for two different texts.

        Returns NEW document bytes; the input is never mutated.

        Raises:
            InvalidVariableMappingError: empty mappings, blank text, variable
                name not matching ``^[a-z_][a-z0-9_]*$``, or two mappings with
                the same exact text.
            MappingTextNotFoundError: at least one mapping text has zero
                occurrences in the document (carries ALL missing texts).
        """
        ...

    @abstractmethod
    async def extract_structure(self, file_bytes: bytes) -> dict:
        """
        Extract the full document structure (body + headers + footers) for preview.

        Returns a dict with three lists of nodes — each node is a paragraph
        containing spans (plain text or placeholder references):

        {
            "headers": [{"kind": "paragraph", "level": 0, "spans": [...]}, ...],
            "body":    [{"kind": "heading",   "level": 1, "spans": [...]}, ...],
            "footers": [{"kind": "paragraph", "level": 0, "spans": [...]}, ...],
        }

        Each span is a dict with the shape {"text": str, "variable": str | None}.
        When `variable` is non-null the span represents a `{{ variable }}` placeholder
        and `text` holds the original placeholder string (e.g. "{{ nombre }}").

        Tables, images and other non-paragraph content are skipped in this
        first iteration — placeholders inside tables still appear in
        `extract_variables` so generation keeps working.
        """
        ...
