from abc import ABC, abstractmethod


class TemplateEngine(ABC):
    @abstractmethod
    async def extract_variables(self, file_bytes: bytes) -> list[str]:
        """Extract variable names from a template file."""
        ...

    @abstractmethod
    async def render(self, file_bytes: bytes, variables: dict[str, str]) -> bytes:
        """Render a template with the given variables. Returns the rendered document bytes."""
        ...
