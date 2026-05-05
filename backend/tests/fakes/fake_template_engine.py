from app.domain.ports.template_engine import TemplateEngine


class FakeTemplateEngine(TemplateEngine):
    """In-memory implementation of TemplateEngine for testing.

    Configurable via constructor arguments:
    - variables_to_return: list of variable name strings returned by extract_variables
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
        """Return variables_to_return formatted as the real engine would."""
        return [
            {"name": name, "contexts": [f"context for {name}"]}
            for name in self.variables_to_return
        ]

    async def render(self, file_bytes: bytes, variables: dict[str, str]) -> bytes:
        if self.should_fail:
            raise RuntimeError("FakeTemplateEngine: render failed (should_fail=True)")
        return self.render_result

    async def validate(self, file_bytes: bytes) -> dict:
        return {"valid": True, "errors": [], "warnings": []}

    async def auto_fix(self, file_bytes: bytes) -> bytes:
        return file_bytes

    async def extract_structure(self, file_bytes: bytes) -> dict:
        return self.structure_to_return
