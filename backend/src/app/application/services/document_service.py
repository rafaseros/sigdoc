from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING
from uuid import UUID

from app.domain.entities import Document
from app.domain.exceptions import (
    BulkLimitExceededError,
    DocumentNotFoundError,
    PdfConversionError,
    TemplateAccessDeniedError,
    TemplateVersionNotFoundError,
    VariablesMismatchError,
)
from app.domain.ports.document_repository import DocumentRepository
from app.domain.ports.storage_service import StorageService
from app.domain.ports.template_engine import TemplateEngine
from app.domain.ports.template_repository import TemplateRepository

if TYPE_CHECKING:
    from app.application.services.audit_service import AuditService
    from app.application.services.quota_service import QuotaService
    from app.application.services.usage_service import UsageService
    from app.domain.ports.pdf_converter import PdfConverter

logger = logging.getLogger(__name__)


class DocumentService:
    TEMPLATES_BUCKET = "templates"
    DOCUMENTS_BUCKET = "documents"

    def __init__(
        self,
        document_repository: DocumentRepository,
        template_repository: TemplateRepository,
        storage: StorageService,
        engine: TemplateEngine,
        pdf_converter: PdfConverter | None = None,
        bulk_generation_limit: int = 10,
        usage_service: UsageService | None = None,
        audit_service: AuditService | None = None,
        ip_address: str | None = None,
        quota_service: QuotaService | None = None,
        tier_id: UUID | None = None,
        user_bulk_override: int | None = None,
    ):
        self._doc_repo = document_repository
        self._tpl_repo = template_repository
        self._storage = storage
        self._engine = engine
        self._pdf_converter = pdf_converter
        self._bulk_limit = bulk_generation_limit
        self._usage_service = usage_service
        self._audit_service = audit_service
        self._ip_address = ip_address
        self._quota_service = quota_service
        self._tier_id = tier_id
        self._user_bulk_override = user_bulk_override

    async def generate_single(
        self,
        template_version_id: str,
        variables: dict[str, str],
        tenant_id: str,
        created_by: str,
        role: str = "user",
    ) -> dict:
        """
        Generate a single document from a template version:
        1. Fetch template version from DB
        2. Check user has access to the template
        3. Download template .docx from MinIO
        4. Render template with variables via docxtpl engine
        5. Upload rendered document to MinIO
        6. Create document record in DB
        7. Return document with presigned download URL
        """
        # 0. Quota check (optional — skipped when quota_service is None)
        if self._quota_service is not None and self._tier_id is not None:
            await self._quota_service.check_document_quota(
                tenant_id=uuid.UUID(tenant_id),
                tier_id=self._tier_id,
                additional=1,
            )

        # 1. Get template version
        version = await self._tpl_repo.get_version_by_id(uuid.UUID(template_version_id))
        if not version:
            raise TemplateVersionNotFoundError(
                f"Template version {template_version_id} not found"
            )

        # 2. Access check
        user_uuid = uuid.UUID(created_by)
        has_access = await self._tpl_repo.has_access(version.template_id, user_uuid, role)
        if not has_access:
            raise TemplateAccessDeniedError("No tenés acceso a esta plantilla")

        # 2. Download template from MinIO
        template_bytes = await self._storage.download_file(
            bucket=self.TEMPLATES_BUCKET,
            path=version.minio_path,
        )

        # 3. Render with docxtpl
        rendered_bytes = await self._engine.render(template_bytes, variables)

        # 4. Upload rendered DOCX to MinIO
        doc_id = uuid.uuid4()
        # Build a filename from the first variable value or use doc_id
        first_var = (
            next(iter(variables.values()), str(doc_id)) if variables else str(doc_id)
        )
        safe_name = "".join(
            c for c in str(first_var) if c.isalnum() or c in " _-"
        ).strip()[:50]
        docx_file_name = f"{safe_name}.docx" if safe_name else f"{doc_id}.docx"

        docx_minio_path = f"{tenant_id}/{doc_id}/{docx_file_name}"
        await self._storage.upload_file(
            bucket=self.DOCUMENTS_BUCKET,
            path=docx_minio_path,
            data=rendered_bytes,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        # 4b. Convert DOCX → PDF (ADR-PDF-03: atomic dual-format)
        pdf_file_name: str | None = None
        pdf_minio_path: str | None = None

        if self._pdf_converter is not None:
            try:
                pdf_bytes = await self._pdf_converter.convert(rendered_bytes)
            except PdfConversionError:
                # Atomic rollback: delete the DOCX we just uploaded (best-effort)
                try:
                    await self._storage.delete_file(self.DOCUMENTS_BUCKET, docx_minio_path)
                except Exception:
                    logger.warning(
                        "Failed to delete orphan DOCX %s after PdfConversionError",
                        docx_minio_path,
                    )
                raise  # re-raise so caller sees PdfConversionError

            # Upload PDF to MinIO
            pdf_stem = docx_file_name[:-5] if docx_file_name.endswith(".docx") else str(doc_id)
            pdf_file_name = f"{pdf_stem}.pdf"
            pdf_minio_path = f"{tenant_id}/{doc_id}/{pdf_file_name}"
            await self._storage.upload_file(
                bucket=self.DOCUMENTS_BUCKET,
                path=pdf_minio_path,
                data=pdf_bytes,
                content_type="application/pdf",
            )

        # 5. Create DB record (domain entity — repo handles ORM mapping)
        document = Document(
            id=doc_id,
            tenant_id=uuid.UUID(tenant_id),
            template_version_id=uuid.UUID(template_version_id),
            docx_minio_path=docx_minio_path,
            docx_file_name=docx_file_name,
            pdf_file_name=pdf_file_name,
            pdf_minio_path=pdf_minio_path,
            generation_type="single",
            variables_snapshot=variables,
            created_by=uuid.UUID(created_by),
            status="completed",
        )
        document = await self._doc_repo.create(document)

        # 6. Record usage + audit (both optional for backward compat)
        user_uuid = uuid.UUID(created_by)
        tenant_uuid = uuid.UUID(tenant_id)
        template_uuid = version.template_id

        if self._usage_service is not None:
            await self._usage_service.record(
                user_id=user_uuid,
                tenant_id=tenant_uuid,
                template_id=template_uuid,
                generation_type="single",
                document_count=1,
            )

        if self._audit_service is not None:
            from app.domain.entities import AuditAction
            audit_details: dict = {}
            if self._pdf_converter is not None:
                audit_details["formats_generated"] = ["docx", "pdf"]
            self._audit_service.log(
                actor_id=user_uuid,
                tenant_id=tenant_uuid,
                action=AuditAction.DOCUMENT_GENERATE,
                resource_type="document",
                resource_id=document.id,
                details=audit_details if audit_details else None,
                ip_address=self._ip_address,
            )

        # 7. Get presigned download URL
        download_url = await self._storage.get_presigned_url(
            bucket=self.DOCUMENTS_BUCKET,
            path=docx_minio_path,
        )

        return {
            "document": document,
            "download_url": download_url,
        }

    async def get_document(self, document_id: uuid.UUID) -> dict:
        """Get document by ID with fresh presigned URL."""
        document = await self._doc_repo.get_by_id(document_id)
        if not document:
            raise DocumentNotFoundError(f"Document {document_id} not found")

        download_url = await self._storage.get_presigned_url(
            bucket=self.DOCUMENTS_BUCKET,
            path=document.docx_minio_path,
        )

        return {
            "document": document,
            "download_url": download_url,
        }

    async def download_document(self, minio_path: str) -> bytes:
        """Download a generated document from MinIO."""
        return await self._storage.download_file(
            bucket=self.DOCUMENTS_BUCKET,
            path=minio_path,
        )

    async def delete_document(self, document_id: uuid.UUID) -> None:
        """Delete a document record and its file from MinIO."""
        document = await self._doc_repo.get_by_id(document_id)
        if not document:
            raise DocumentNotFoundError(f"Document {document_id} not found")
        # Delete from MinIO
        try:
            await self._storage.delete_file(self.DOCUMENTS_BUCKET, document.docx_minio_path)
        except Exception:
            pass  # File may already be gone
        # Delete from DB
        await self._doc_repo.delete(document_id)

        # Audit the deletion (optional for backward compat)
        if self._audit_service is not None:
            from app.domain.entities import AuditAction
            self._audit_service.log(
                actor_id=document.created_by,
                tenant_id=document.tenant_id,
                action=AuditAction.DOCUMENT_DELETE,
                resource_type="document",
                resource_id=document_id,
                ip_address=self._ip_address,
            )

    async def list_documents(
        self,
        page: int = 1,
        size: int = 20,
        template_id: str | None = None,
        created_by: str | None = None,
    ) -> tuple[list, int]:
        """List documents with pagination."""
        tpl_uuid = uuid.UUID(template_id) if template_id else None
        created_by_uuid = uuid.UUID(created_by) if created_by else None
        return await self._doc_repo.list_paginated(
            page=page, size=size, template_id=tpl_uuid, created_by=created_by_uuid
        )

    async def list_documents_by_batch(
        self, batch_id: UUID, tenant_id: UUID
    ) -> list:
        """Return all documents for a given batch, scoped to tenant.

        Public delegator for DocumentRepository.list_by_batch_id.
        Replaces the private _doc_repo access pattern used in the bulk
        download endpoint (W-PRES-02 fix). O(batch_size) instead of O(N total).
        """
        return await self._doc_repo.list_by_batch_id(batch_id=batch_id, tenant_id=tenant_id)

    # ── Bulk generation methods ──────────────────────────────────────────

    async def generate_excel_template(
        self,
        template_version_id: str,
        user_id: str | None = None,
        role: str = "user",
    ) -> tuple[bytes, str]:
        """
        Generate a blank Excel template for bulk data entry.
        Column headers = template variable names.
        Returns (excel_bytes, filename).
        """
        import openpyxl
        from io import BytesIO
        from openpyxl.styles import Alignment, Font, PatternFill

        version = await self._tpl_repo.get_version_by_id(
            uuid.UUID(template_version_id)
        )
        if not version:
            raise TemplateVersionNotFoundError(
                f"Template version {template_version_id} not found"
            )

        if user_id is not None:
            user_uuid = uuid.UUID(user_id)
            has_access = await self._tpl_repo.has_access(
                version.template_id, user_uuid, role
            )
            if not has_access:
                raise TemplateAccessDeniedError("No tenés acceso a esta plantilla")

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Data"

        variables = version.variables  # list of variable names

        # Header row with styling
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="366092", fill_type="solid")

        for col, var_name in enumerate(variables, 1):
            cell = ws.cell(row=1, column=col, value=var_name)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center")
            ws.column_dimensions[cell.column_letter].width = max(
                len(var_name) + 4, 15
            )

        output = BytesIO()
        wb.save(output)
        output.seek(0)

        # Build filename from template name
        template = await self._tpl_repo.get_by_id(version.template_id)
        safe_name = "".join(
            c for c in template.name if c.isalnum() or c in " _-"
        ).strip()
        filename = f"{safe_name}_bulk_template.xlsx"

        return output.read(), filename

    async def parse_excel_data(
        self,
        template_version_id: str,
        excel_bytes: bytes,
        user_id: str | None = None,
        role: str = "user",
        tenant_id: str | None = None,
        user_bulk_override: int | None = None,
    ) -> list[dict[str, str]]:
        """
        Parse a filled Excel file and validate against template variables.
        Returns list of dicts (one per row).
        Raises BulkLimitExceededError if > bulk_limit rows (when quota_service is None).
        Raises QuotaExceededError if > tier/user bulk limit (when quota_service is set).
        Raises VariablesMismatchError if headers don't match template variables.
        Raises TemplateAccessDeniedError if user lacks access.
        """
        import openpyxl
        from io import BytesIO

        version = await self._tpl_repo.get_version_by_id(
            uuid.UUID(template_version_id)
        )
        if not version:
            raise TemplateVersionNotFoundError(
                f"Template version {template_version_id} not found"
            )

        if user_id is not None:
            user_uuid = uuid.UUID(user_id)
            has_access = await self._tpl_repo.has_access(
                version.template_id, user_uuid, role
            )
            if not has_access:
                raise TemplateAccessDeniedError("No tenés acceso a esta plantilla")

        wb = openpyxl.load_workbook(BytesIO(excel_bytes))
        ws = wb.active

        # Read headers from first row
        headers = [cell.value for cell in ws[1] if cell.value is not None]

        # Validate headers match template variables
        expected = set(version.variables)
        actual = set(headers)
        if expected != actual:
            missing = expected - actual
            extra = actual - expected
            raise VariablesMismatchError(
                f"Header mismatch. Missing: {missing or 'none'}. "
                f"Extra: {extra or 'none'}"
            )

        # Parse data rows
        rows: list[dict[str, str]] = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            if all(v is None for v in row):
                continue
            row_dict = {}
            for header, value in zip(headers, row):
                row_dict[header] = str(value) if value is not None else ""
            rows.append(row_dict)

        if len(rows) == 0:
            raise VariablesMismatchError("Excel file has no data rows")

        # Bulk limit check — quota_service takes precedence over legacy _bulk_limit
        if self._quota_service is not None and self._tier_id is not None:
            effective_tenant_id = uuid.UUID(tenant_id) if tenant_id else None
            if effective_tenant_id is not None:
                await self._quota_service.check_bulk_limit(
                    tenant_id=effective_tenant_id,
                    tier_id=self._tier_id,
                    requested_count=len(rows),
                    user_bulk_override=user_bulk_override,
                )
        else:
            if len(rows) > self._bulk_limit:
                raise BulkLimitExceededError(limit=self._bulk_limit)

        return rows

    async def generate_bulk(
        self,
        template_version_id: str,
        rows: list[dict[str, str]],
        tenant_id: str,
        created_by: str,
        role: str = "user",
    ) -> dict:
        """
        Generate multiple documents from template + data rows.
        Returns dict with batch_id, zip_path, document_count, and errors.
        """
        import zipfile
        from io import BytesIO

        # 0. Quota checks (optional — skipped when quota_service is None)
        if self._quota_service is not None and self._tier_id is not None:
            tenant_uuid = uuid.UUID(tenant_id)
            await self._quota_service.check_document_quota(
                tenant_id=tenant_uuid,
                tier_id=self._tier_id,
                additional=len(rows),
            )
            await self._quota_service.check_bulk_limit(
                tenant_id=tenant_uuid,
                tier_id=self._tier_id,
                requested_count=len(rows),
                user_bulk_override=self._user_bulk_override,
            )

        version = await self._tpl_repo.get_version_by_id(
            uuid.UUID(template_version_id)
        )
        if not version:
            raise TemplateVersionNotFoundError(
                f"Template version {template_version_id} not found"
            )

        # Access check
        user_uuid = uuid.UUID(created_by)
        has_access = await self._tpl_repo.has_access(version.template_id, user_uuid, role)
        if not has_access:
            raise TemplateAccessDeniedError("No tenés acceso a esta plantilla")

        # Download template ONCE — engine creates a fresh DocxTemplate per render
        template_bytes = await self._storage.download_file(
            bucket=self.TEMPLATES_BUCKET,
            path=version.minio_path,
        )

        batch_id = uuid.uuid4()
        zip_buffer = BytesIO()
        documents = []
        # Track all MinIO keys uploaded so far for rollback on failure (ADR-PDF-03 bulk)
        uploaded_minio_paths: list[str] = []

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, row_data in enumerate(rows):
                # Render document (fresh DocxTemplate per render — handled by engine)
                rendered_bytes = await self._engine.render(template_bytes, row_data)

                # Generate filename from first variable value
                first_var = next(iter(row_data.values()), f"doc_{i + 1}")
                safe_name = "".join(
                    c for c in str(first_var) if c.isalnum() or c in " _-"
                ).strip()[:50]
                docx_file_name = (
                    f"{i + 1:03d}_{safe_name}.docx"
                    if safe_name
                    else f"{i + 1:03d}_document.docx"
                )

                zf.writestr(docx_file_name, rendered_bytes)

                doc_id = uuid.uuid4()
                docx_minio_path = f"{tenant_id}/{batch_id}/{docx_file_name}"

                # Upload DOCX to MinIO
                await self._storage.upload_file(
                    bucket=self.DOCUMENTS_BUCKET,
                    path=docx_minio_path,
                    data=rendered_bytes,
                    content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
                uploaded_minio_paths.append(docx_minio_path)

                # Convert DOCX → PDF (ADR-PDF-03 bulk: atomic, sequential)
                pdf_file_name: str | None = None
                pdf_minio_path: str | None = None

                if self._pdf_converter is not None:
                    try:
                        pdf_bytes = await self._pdf_converter.convert(rendered_bytes)
                    except PdfConversionError:
                        # Rollback: delete ALL uploaded files for this batch
                        for path in uploaded_minio_paths:
                            try:
                                await self._storage.delete_file(
                                    self.DOCUMENTS_BUCKET, path
                                )
                            except Exception:
                                logger.warning(
                                    "Failed to delete bulk upload %s during rollback",
                                    path,
                                )
                        raise  # propagate — no DB rows persisted

                    # Upload PDF to MinIO
                    pdf_stem = (
                        docx_file_name[:-5]
                        if docx_file_name.endswith(".docx")
                        else f"{doc_id}"
                    )
                    pdf_file_name = f"{pdf_stem}.pdf"
                    pdf_minio_path = f"{tenant_id}/{batch_id}/{pdf_file_name}"
                    await self._storage.upload_file(
                        bucket=self.DOCUMENTS_BUCKET,
                        path=pdf_minio_path,
                        data=pdf_bytes,
                        content_type="application/pdf",
                    )
                    uploaded_minio_paths.append(pdf_minio_path)

                # Build domain entity (not persisted until all rows succeed)
                doc = Document(
                    id=doc_id,
                    tenant_id=uuid.UUID(tenant_id),
                    template_version_id=uuid.UUID(template_version_id),
                    docx_minio_path=docx_minio_path,
                    docx_file_name=docx_file_name,
                    pdf_file_name=pdf_file_name,
                    pdf_minio_path=pdf_minio_path,
                    generation_type="bulk",
                    batch_id=batch_id,
                    variables_snapshot=row_data,
                    created_by=uuid.UUID(created_by),
                    status="completed",
                )
                documents.append(doc)

        zip_buffer.seek(0)
        zip_bytes = zip_buffer.read()

        # Upload ZIP to MinIO
        zip_path = f"{tenant_id}/{batch_id}/bulk.zip"
        await self._storage.upload_file(
            bucket=self.DOCUMENTS_BUCKET,
            path=zip_path,
            data=zip_bytes,
            content_type="application/zip",
        )

        # Save document records to DB (all rows succeeded — persist atomically)
        if documents:
            await self._doc_repo.create_batch(documents)

        # Record usage + audit (both optional for backward compat)
        success_count = len(documents)
        user_uuid = uuid.UUID(created_by)
        tenant_uuid = uuid.UUID(tenant_id)
        template_uuid = version.template_id

        if self._usage_service is not None and success_count > 0:
            await self._usage_service.record(
                user_id=user_uuid,
                tenant_id=tenant_uuid,
                template_id=template_uuid,
                generation_type="bulk",
                document_count=success_count,
            )

        if self._audit_service is not None:
            from app.domain.entities import AuditAction
            audit_details: dict = {
                "document_count": success_count,
            }
            if self._pdf_converter is not None:
                audit_details["formats_generated"] = ["docx", "pdf"]
            self._audit_service.log(
                actor_id=user_uuid,
                tenant_id=tenant_uuid,
                action=AuditAction.DOCUMENT_GENERATE_BULK,
                resource_type="document_batch",
                resource_id=batch_id,
                details=audit_details,
                ip_address=self._ip_address,
            )

        return {
            "batch_id": batch_id,
            "zip_path": zip_path,
            "document_count": success_count,
            "errors": [],
        }

    # ── Lazy PDF backfill ───────────────────────────────────────────────────

    async def ensure_pdf(self, document_id: UUID) -> Document:
        """Lazily generate and persist a PDF for a legacy DOCX-only document.

        ADR-PDF-04 contract:
        - Fast path (idempotent): if pdf_file_name is already set, return
          the document immediately without calling the converter.
        - Slow path: download DOCX bytes, convert to PDF, upload PDF, update
          document row via update_pdf_fields(), return updated document.
        - On PdfConversionError: do NOT delete DOCX, do NOT update DB, let
          exception propagate so the presentation layer maps it to HTTP 503.

        Concurrency note: two concurrent requests for the same legacy doc may
        both run the slow path (last-write-wins). The PDF bytes are
        deterministic (same DOCX input → same PDF output for a given Gotenberg
        version), so duplicate uploads are tolerable and the row ends up in a
        consistent state either way.

        Returns:
            The updated Document with pdf_file_name and pdf_minio_path set.

        Raises:
            DocumentNotFoundError: if document_id does not exist.
            PdfConversionError: if converter fails (pdf_file_name remains NULL).
        """
        document = await self._doc_repo.get_by_id(document_id)
        if document is None:
            raise DocumentNotFoundError(f"Document {document_id} not found")

        # Fast path — already has PDF (idempotent)
        if document.pdf_file_name is not None:
            return document

        # Slow path — backfill
        if self._pdf_converter is None:
            raise PdfConversionError(
                "PdfConverter not configured — cannot backfill PDF"
            )

        # Download DOCX from MinIO (raises FileNotFoundError on missing file)
        docx_bytes = await self._storage.download_file(
            bucket=self.DOCUMENTS_BUCKET,
            path=document.docx_minio_path,
        )

        # Convert — propagate PdfConversionError without touching DB or MinIO
        pdf_bytes = await self._pdf_converter.convert(docx_bytes)

        # Derive PDF path from DOCX path (deterministic key for idempotency)
        docx_minio_path = document.docx_minio_path
        if docx_minio_path.endswith(".docx"):
            pdf_minio_path = docx_minio_path[:-5] + ".pdf"
        else:
            pdf_minio_path = docx_minio_path + ".pdf"

        pdf_file_name = (
            document.docx_file_name[:-5] + ".pdf"
            if document.docx_file_name.endswith(".docx")
            else document.docx_file_name + ".pdf"
        )

        # Upload PDF to MinIO
        await self._storage.upload_file(
            bucket=self.DOCUMENTS_BUCKET,
            path=pdf_minio_path,
            data=pdf_bytes,
            content_type="application/pdf",
        )

        # Persist update (S-02 resolution: update_pdf_fields returns a domain
        # Document so callers do not need to handle ORM objects directly)
        updated = await self._doc_repo.update_pdf_fields(
            doc_id=document_id,
            pdf_file_name=pdf_file_name,
            pdf_minio_path=pdf_minio_path,
        )

        # The real repo returns a DocumentModel (ORM object); fake returns
        # the updated domain Document. Phase 4 callers only need the
        # pdf_minio_path string from the returned object — both ORM and
        # domain entity expose this attribute with the same name, so the
        # presentation layer works transparently with either type.
        return updated
