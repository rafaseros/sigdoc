from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.document_service import DocumentService
from app.application.services.template_service import TemplateService
from app.infrastructure.persistence.repositories.template_repository import (
    SQLAlchemyTemplateRepository,
)
from app.infrastructure.storage import get_storage_service
from app.infrastructure.templating import get_template_engine
from app.presentation.middleware.tenant import get_tenant_session


async def get_template_service(
    session: AsyncSession = Depends(get_tenant_session),
) -> TemplateService:
    return TemplateService(
        repository=SQLAlchemyTemplateRepository(session),
        storage=get_storage_service(),
        engine=get_template_engine(),
    )


async def get_document_service(
    session: AsyncSession = Depends(get_tenant_session),
) -> DocumentService:
    from app.infrastructure.persistence.repositories.document_repository import (
        SQLAlchemyDocumentRepository,
    )

    return DocumentService(
        document_repository=SQLAlchemyDocumentRepository(session),
        template_repository=SQLAlchemyTemplateRepository(session),
        storage=get_storage_service(),
        engine=get_template_engine(),
    )
