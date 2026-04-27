from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.auth.jwt_handler import decode_token
from app.infrastructure.persistence.database import get_session

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


class CurrentUser:
    """Holds the authenticated user's context extracted from JWT."""

    def __init__(self, user_id: UUID, tenant_id: UUID, role: str):
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.role = role


async def get_current_user(token: str = Depends(oauth2_scheme)) -> CurrentUser:
    """Extract and validate user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        tenant_id = payload.get("tenant_id")
        token_type = payload.get("type")

        if user_id is None or tenant_id is None:
            raise credentials_exception
        if token_type != "access":
            raise credentials_exception

        return CurrentUser(
            user_id=UUID(user_id),
            tenant_id=UUID(tenant_id),
            role=payload.get("role", "document_generator"),
        )
    except JWTError:
        raise credentials_exception


async def get_tenant_session(
    current_user: CurrentUser = Depends(get_current_user),
) -> AsyncSession:
    """Get a DB session with tenant context from the authenticated user."""
    async for session in get_session():
        session.info["tenant_id"] = current_user.tenant_id
        yield session
