class DomainError(Exception):
    """Base domain error."""


class TemplateNotFoundError(DomainError):
    """Template not found."""


class TemplateVersionNotFoundError(DomainError):
    """Template version not found."""


class TemplateVersionFileNotFoundError(DomainError):
    """Related file not found, or does not belong to the given template version.

    Never distinguishes between "does not exist" and "belongs to a different
    version" — the 404 never leaks the existence of a file under a foreign
    version_id (mirrors TemplatePresetNotFoundError).
    """


class DocumentNotFoundError(DomainError):
    """Document not found."""


class InvalidTemplateError(DomainError):
    """Invalid template file."""


class TemplateRenderError(DomainError):
    """A template could not be rendered safely.

    Raised by template engines when a template triggers a Jinja error at
    render time — most importantly a sandbox ``SecurityError`` (e.g. an
    uploaded .docx containing an unsafe expression such as attribute access
    into Python internals: ``{{ x.__class__.__mro__ }}`` /
    ``{{ cycler.__init__.__globals__ }}``), but also ``UndefinedError`` or
    any other ``TemplateError``. The engine catches the raw Jinja exception
    and raises this domain error so the API layer can return a non-leaking
    4xx instead of an uncaught 500. The message is intentionally generic and
    never echoes the offending expression or internal state."""


class BulkLimitExceededError(DomainError):
    """Bulk generation limit exceeded."""
    def __init__(self, limit: int = 10):
        super().__init__(f"Bulk generation limited to {limit} documents")
        self.limit = limit


class VariablesMismatchError(DomainError):
    """Variables in data don't match template variables."""


class InvalidSpreadsheetError(DomainError):
    """An uploaded spreadsheet could not be opened or parsed.

    Raised by the service layer when ``openpyxl.load_workbook`` (or the
    subsequent worksheet access) fails on malformed input — e.g. a non-zip
    file, or a valid zip that is not an .xlsx (a .docx renamed to .xlsx passes
    the extension check but is missing the required workbook parts). openpyxl
    surfaces these as ``zipfile.BadZipFile``, ``KeyError``, or
    ``InvalidFileException``; the service catches the raw exception and raises
    this domain error so the API layer can return a clean 400 instead of an
    uncaught 500. The message is user-facing (Spanish) and never echoes
    internal parser state."""


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


class InvalidVariableMappingError(DomainError):
    """A text-to-variable mapping list is structurally invalid.

    Raised by template engines before rewriting an example document when the
    mappings are empty, a text is blank, a variable name is not lowercase
    snake_case, or two mappings share the same exact text.
    """


class MappingTextNotFoundError(DomainError):
    """One or more mapping texts were not found anywhere in the example document.

    Carries `missing_texts` (every text that had zero occurrences, in the
    original mapping order) so the API layer can return a 422 listing them all.
    """

    def __init__(self, missing_texts: list[str]) -> None:
        joined = ", ".join(f"'{t}'" for t in missing_texts)
        super().__init__(
            f"Los siguientes textos no se encontraron en el documento: {joined}"
        )
        self.missing_texts = list(missing_texts)


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
