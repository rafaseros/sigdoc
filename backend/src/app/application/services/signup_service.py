"""SignupService — atomic self-service tenant onboarding.

Spec: REQ-SIGNUP-01 through REQ-SIGNUP-11
Design: ADR-SIGNUP-01 through ADR-SIGNUP-05

Flow (all within a single DB transaction managed by the caller's session):
    1. Check global email uniqueness (explicit check before DB constraint)
    2. Check organization name uniqueness
    3. Generate slug from org name (with dedup)
    4. Resolve Free tier by slug lookup
    5. Create Tenant
    6. Create User (admin role, hashed password)
    7. Fire-and-forget audit log
    8. Return JWT tokens + user info
"""

import uuid
from dataclasses import dataclass

from app.application.services.slug_utils import slugify, unique_slug
from app.domain.entities.audit_log import AuditAction
from app.domain.entities.subscription_tier import FREE_TIER_ID
from app.domain.entities.tenant import Tenant
from app.domain.entities.user import User
from app.domain.ports.subscription_tier_repository import SubscriptionTierRepository
from app.domain.ports.tenant_repository import TenantRepository
from app.domain.ports.user_repository import UserRepository
from app.infrastructure.auth.jwt_handler import (
    create_access_token,
    create_refresh_token,
    hash_password,
)


class SignupError(Exception):
    """Raised when signup cannot proceed due to a business rule violation."""

    def __init__(self, message: str, field: str) -> None:
        super().__init__(message)
        self.field = field  # "email" | "organization_name"


@dataclass
class SignupResult:
    access_token: str
    refresh_token: str
    user: User


class SignupService:
    """Orchestrates atomic signup: tenant + admin user creation in one transaction.

    ADR-SIGNUP-01: Uses the caller's session (same pattern as auth.py login endpoint).
    The session is committed by the FastAPI get_session dependency after the handler
    returns successfully — this gives us the atomicity guarantee.
    """

    def __init__(
        self,
        tenant_repo: TenantRepository,
        user_repo: UserRepository,
        tier_repo: SubscriptionTierRepository,
        audit_service=None,  # AuditService | None — optional for testability
    ) -> None:
        self._tenant_repo = tenant_repo
        self._user_repo = user_repo
        self._tier_repo = tier_repo
        self._audit_service = audit_service

    async def signup(
        self,
        email: str,
        password: str,
        full_name: str,
        org_name: str,
        ip_address: str | None = None,
    ) -> SignupResult:
        """Create a new tenant + admin user atomically.

        Raises:
            SignupError: if email or org_name already exists.
        """
        # Step 1: Global email uniqueness check (ADR-SIGNUP-02)
        existing_user = await self._user_repo.get_by_email(email)
        if existing_user is not None:
            raise SignupError("Email already registered", field="email")

        # Step 2: Org name uniqueness check
        existing_tenant = await self._tenant_repo.get_by_name(org_name)
        if existing_tenant is not None:
            raise SignupError("Organization name already taken", field="organization_name")

        # Step 3: Generate unique slug (ADR-SIGNUP-03: check-then-create)
        base_slug = slugify(org_name)

        async def slug_taken(s: str) -> bool:
            return await self._tenant_repo.get_by_slug(s) is not None

        tenant_slug = await unique_slug(base_slug, slug_taken)

        # Step 4: Resolve Free tier by slug lookup (ADR-SIGNUP-05)
        free_tier = await self._tier_repo.get_by_slug("free")
        tier_id = free_tier.id if free_tier is not None else FREE_TIER_ID

        # Step 5: Create Tenant
        tenant_id = uuid.uuid4()
        tenant = Tenant(
            id=tenant_id,
            name=org_name,
            slug=tenant_slug,
            is_active=True,
            tier_id=tier_id,
        )
        tenant = await self._tenant_repo.create(tenant)

        # Step 6: Create User (admin role, hashed password)
        user_id = uuid.uuid4()
        hashed = hash_password(password)
        user = User(
            id=user_id,
            tenant_id=tenant_id,
            email=email,
            hashed_password=hashed,
            full_name=full_name,
            role="admin",
            is_active=True,
        )
        user = await self._user_repo.create(user)

        # Step 7: Fire-and-forget audit log
        if self._audit_service is not None:
            self._audit_service.log(
                actor_id=user_id,
                tenant_id=tenant_id,
                action=AuditAction.AUTH_SIGNUP,
                resource_type="tenant",
                resource_id=tenant_id,
                ip_address=ip_address,
            )

        # Step 8: Return JWT tokens
        access_token = create_access_token(
            user_id=str(user_id),
            tenant_id=str(tenant_id),
            role="admin",
        )
        refresh_token = create_refresh_token(
            user_id=str(user_id),
            tenant_id=str(tenant_id),
        )

        return SignupResult(
            access_token=access_token,
            refresh_token=refresh_token,
            user=user,
        )
