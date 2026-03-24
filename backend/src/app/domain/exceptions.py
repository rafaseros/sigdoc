class DomainError(Exception):
    """Base domain error."""


class TemplateNotFoundError(DomainError):
    """Template not found."""


class TemplateVersionNotFoundError(DomainError):
    """Template version not found."""


class DocumentNotFoundError(DomainError):
    """Document not found."""


class InvalidTemplateError(DomainError):
    """Invalid template file."""


class BulkLimitExceededError(DomainError):
    """Bulk generation limit exceeded."""
    def __init__(self, limit: int = 10):
        super().__init__(f"Bulk generation limited to {limit} documents")
        self.limit = limit


class VariablesMismatchError(DomainError):
    """Variables in data don't match template variables."""
