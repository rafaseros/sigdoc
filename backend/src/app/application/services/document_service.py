import uuid

from app.domain.exceptions import (
    BulkLimitExceededError,
    DocumentNotFoundError,
    TemplateVersionNotFoundError,
    VariablesMismatchError,
)
from app.domain.ports.document_repository import DocumentRepository
from app.domain.ports.storage_service import StorageService
from app.domain.ports.template_engine import TemplateEngine
from app.domain.ports.template_repository import TemplateRepository


class DocumentService:
    TEMPLATES_BUCKET = "templates"
    DOCUMENTS_BUCKET = "documents"

    def __init__(
        self,
        document_repository: DocumentRepository,
        template_repository: TemplateRepository,
        storage: StorageService,
        engine: TemplateEngine,
    ):
        self._doc_repo = document_repository
        self._tpl_repo = template_repository
        self._storage = storage
        self._engine = engine

    async def generate_single(
        self,
        template_version_id: str,
        variables: dict[str, str],
        tenant_id: str,
        created_by: str,
    ) -> dict:
        """
        Generate a single document from a template version:
        1. Fetch template version from DB
        2. Download template .docx from MinIO
        3. Render template with variables via docxtpl engine
        4. Upload rendered document to MinIO
        5. Create document record in DB
        6. Return document with presigned download URL
        """
        # 1. Get template version
        version = await self._tpl_repo.get_version_by_id(uuid.UUID(template_version_id))
        if not version:
            raise TemplateVersionNotFoundError(
                f"Template version {template_version_id} not found"
            )

        # 2. Download template from MinIO
        template_bytes = await self._storage.download_file(
            bucket=self.TEMPLATES_BUCKET,
            path=version.minio_path,
        )

        # 3. Render with docxtpl
        rendered_bytes = await self._engine.render(template_bytes, variables)

        # 4. Upload rendered document to MinIO
        doc_id = uuid.uuid4()
        # Build a filename from the first variable value or use doc_id
        first_var = (
            next(iter(variables.values()), str(doc_id)) if variables else str(doc_id)
        )
        safe_name = "".join(
            c for c in str(first_var) if c.isalnum() or c in " _-"
        ).strip()[:50]
        file_name = f"{safe_name}.docx" if safe_name else f"{doc_id}.docx"

        minio_path = f"{tenant_id}/{doc_id}/{file_name}"
        await self._storage.upload_file(
            bucket=self.DOCUMENTS_BUCKET,
            path=minio_path,
            data=rendered_bytes,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        # 5. Create DB record
        from app.infrastructure.persistence.models.document import DocumentModel

        document = DocumentModel(
            id=doc_id,
            tenant_id=uuid.UUID(tenant_id),
            template_version_id=uuid.UUID(template_version_id),
            minio_path=minio_path,
            file_name=file_name,
            generation_type="single",
            variables_snapshot=variables,
            created_by=uuid.UUID(created_by),
            status="completed",
        )
        document = await self._doc_repo.create(document)

        # 6. Get presigned download URL
        download_url = await self._storage.get_presigned_url(
            bucket=self.DOCUMENTS_BUCKET,
            path=minio_path,
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
            path=document.minio_path,
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
            await self._storage.delete_file(self.DOCUMENTS_BUCKET, document.minio_path)
        except Exception:
            pass  # File may already be gone
        # Delete from DB
        await self._doc_repo.delete(document_id)

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

    # ── Bulk generation methods ──────────────────────────────────────────

    async def generate_excel_template(
        self, template_version_id: str
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
        self, template_version_id: str, excel_bytes: bytes
    ) -> list[dict[str, str]]:
        """
        Parse a filled Excel file and validate against template variables.
        Returns list of dicts (one per row).
        Raises BulkLimitExceededError if > 10 rows.
        Raises VariablesMismatchError if headers don't match template variables.
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

        if len(rows) > 10:
            raise BulkLimitExceededError(limit=10)

        if len(rows) == 0:
            raise VariablesMismatchError("Excel file has no data rows")

        return rows

    async def generate_bulk(
        self,
        template_version_id: str,
        rows: list[dict[str, str]],
        tenant_id: str,
        created_by: str,
    ) -> dict:
        """
        Generate multiple documents from template + data rows.
        Returns dict with batch_id, zip_path, document_count, and errors.
        """
        import zipfile
        from io import BytesIO

        version = await self._tpl_repo.get_version_by_id(
            uuid.UUID(template_version_id)
        )
        if not version:
            raise TemplateVersionNotFoundError(
                f"Template version {template_version_id} not found"
            )

        # Download template ONCE — engine creates a fresh DocxTemplate per render
        template_bytes = await self._storage.download_file(
            bucket=self.TEMPLATES_BUCKET,
            path=version.minio_path,
        )

        batch_id = uuid.uuid4()
        zip_buffer = BytesIO()
        results: dict[str, list] = {"success": [], "errors": []}
        documents = []

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, row_data in enumerate(rows):
                try:
                    # Render document (fresh DocxTemplate per render — handled by engine)
                    rendered_bytes = await self._engine.render(
                        template_bytes, row_data
                    )

                    # Generate filename from first variable value
                    first_var = next(iter(row_data.values()), f"doc_{i + 1}")
                    safe_name = "".join(
                        c
                        for c in str(first_var)
                        if c.isalnum() or c in " _-"
                    ).strip()[:50]
                    file_name = (
                        f"{i + 1:03d}_{safe_name}.docx"
                        if safe_name
                        else f"{i + 1:03d}_document.docx"
                    )

                    zf.writestr(file_name, rendered_bytes)

                    # Create document record
                    from app.infrastructure.persistence.models.document import (
                        DocumentModel,
                    )

                    doc_id = uuid.uuid4()
                    doc = DocumentModel(
                        id=doc_id,
                        tenant_id=uuid.UUID(tenant_id),
                        template_version_id=uuid.UUID(template_version_id),
                        minio_path=f"{tenant_id}/{batch_id}/{file_name}",
                        file_name=file_name,
                        generation_type="bulk",
                        batch_id=batch_id,
                        variables_snapshot=row_data,
                        created_by=uuid.UUID(created_by),
                        status="completed",
                    )
                    documents.append(doc)
                    results["success"].append(
                        {"row": i + 1, "file": file_name}
                    )

                except Exception as e:
                    results["errors"].append({"row": i + 1, "error": str(e)})

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

        # Save document records to DB
        if documents:
            await self._doc_repo.create_batch(documents)

        return {
            "batch_id": batch_id,
            "zip_path": zip_path,
            "document_count": len(results["success"]),
            "errors": results["errors"],
        }
