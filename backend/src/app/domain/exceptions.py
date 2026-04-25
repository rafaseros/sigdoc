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


class TemplateAccessDeniedError(DomainError):
    """User does not have access to the requested template."""


class TemplateSharingError(DomainError):
    """Template sharing operation failed (e.g. cross-tenant share attempt)."""


class QuotaExceededError(DomainError):
    """Subscription quota exceeded for the tenant."""

    def __init__(
        self,
        limit_type: str,
        limit_value: int | None,
        current_usage: int,
        tier_name: str,
    ) -> None:
        super().__init__(
            f"Quota exceeded: {limit_type} limit is {limit_value}, "
            f"current usage is {current_usage} (tier: {tier_name})"
        )
        self.limit_type = limit_type
        self.limit_value = limit_value
        self.current_usage = current_usage
        self.tier_name = tier_name


class PdfConversionError(DomainError):
    """PDF conversion failed.

    Raised by PdfConverter implementations for any conversion failure:
    HTTP errors, network errors, empty input, or unexpected Gotenberg responses.
    Must NOT be defined in the infrastructure layer (REQ-PDF-06).
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
