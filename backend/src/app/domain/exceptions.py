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


class TemplateNameCollisionError(DomainError):
    """A template create/rename collided with an existing (tenant_id, name) pair.

    Raised by repository implementations instead of leaking the underlying
    persistence exception (e.g. sqlalchemy.exc.IntegrityError). The service
    layer is expected to catch this and map it to a non-leaking, user-facing
    message.
    """

    def __init__(self, name: str | None = None) -> None:
        super().__init__(f"Template name collision for '{name}'")
        self.name = name


class TemplateFolderNotFoundError(DomainError):
    """Template folder not found, or not owned by the requesting user.

    Folders are strictly personal — this error is also raised when a caller
    tries to act on another user's folder, so the 404 never leaks whether
    the folder exists under a different owner.
    """


class FolderNameCollisionError(DomainError):
    """A folder create/rename collided with an existing (tenant_id, owner_id, name) pair.

    Raised by repository implementations instead of leaking the underlying
    persistence exception (e.g. sqlalchemy.exc.IntegrityError). The service
    layer is expected to catch this and map it to a non-leaking, user-facing
    message. Mirrors TemplateNameCollisionError.
    """

    def __init__(self, name: str | None = None) -> None:
        super().__init__(f"Folder name collision for '{name}'")
        self.name = name


class PresetNameCollisionError(DomainError):
    """A preset create/rename collided with an existing (template_id, name) pair.

    Raised by repository implementations instead of leaking the underlying
    persistence exception (e.g. sqlalchemy.exc.IntegrityError). The service
    layer is expected to catch this and map it to a non-leaking, user-facing
    message. Mirrors TemplateNameCollisionError / FolderNameCollisionError.
    """

    def __init__(self, name: str | None = None) -> None:
        super().__init__(f"Preset name collision for '{name}'")
        self.name = name


class TemplatePresetNotFoundError(DomainError):
    """Template preset not found, or does not belong to the given template.

    Never distinguishes between "does not exist" and "belongs to a
    different template" — the 404 never leaks the existence of a preset
    under a foreign template_id.
    """


class ComputedVariableValidationError(DomainError):
    """A computed-variable spec failed cross-variable validation when saving
    variables_meta (e.g. unknown/non-numeric/self-referencing/chained source).

    Raised by the service layer (not pydantic) because these rules require
    full context of the version's merged variables_meta, not just the shape
    of a single field.
    """


class ComputedVariableError(DomainError):
    """A computed variable failed to resolve at generation/preview time.

    Distinct from ComputedVariableValidationError (raised at save-time):
    this is raised when the source value is present and parseable but is
    out of the supported domain for the configured function (e.g.
    number_to_words with a negative or too-large source).
    """


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
