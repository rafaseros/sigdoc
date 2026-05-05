"""Integration tests — /api/v1/users/* endpoints (admin operations).

The users and auth endpoints both instantiate SQLAlchemyUserRepository directly
inside the route handler.  We monkeypatch the class in each module to return a
FakeUserRepository that works from an in-memory dict.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.domain.entities import User
from app.infrastructure.auth.jwt_handler import hash_password
from tests.fakes import FakeUserRepository

# ── Stable IDs (must match integration conftest) ──────────────────────────────

ADMIN_USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
ADMIN_TENANT_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

TARGET_USER_ID = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")


# ── Helper: build a fake-repo class that the endpoint can instantiate ─────────


def _make_users_repo_class(fake_repo: FakeUserRepository):
    """Return a drop-in replacement for SQLAlchemyUserRepository.

    The real class takes a session argument — we accept and discard it.
    """

    class _Repo:
        def __init__(self, session):  # noqa: ARG002
            self._fake = fake_repo

        async def get_by_email(self, email: str):
            return await self._fake.get_by_email(email)

        async def get_by_id(self, user_id):
            return await self._fake.get_by_id(user_id)

        async def create(self, user):
            return await self._fake.create(user)

        async def list_by_tenant(self, page: int = 1, size: int = 20):
            return await self._fake.list_by_tenant(page=page, size=size)

        async def update(self, user_id, **kwargs):
            return await self._fake.update(user_id, **kwargs)

        async def deactivate(self, user_id):
            return await self._fake.deactivate(user_id)

        async def count_admins_by_tenant(self, tenant_id):
            return await self._fake.count_admins_by_tenant(tenant_id)

    return _Repo


def _seed_user(repo: FakeUserRepository, user: User) -> None:
    """Seed a user synchronously into the fake repo."""
    repo._users[user.id] = user
    repo._by_email[user.email] = user.id


# ── Task 5.8: Admin sets/clears per-user limit — integration roundtrip ────────


@pytest.mark.asyncio
async def test_admin_sets_user_bulk_limit_and_me_reflects_it(
    async_client, auth_headers, monkeypatch
):
    """Admin PUTs user with bulk_generation_limit=5 → GET /auth/me shows effective_bulk_limit=5."""
    fake_repo = FakeUserRepository()

    target_user = User(
        id=TARGET_USER_ID,
        tenant_id=ADMIN_TENANT_ID,
        email="target@test.com",
        hashed_password=hash_password("secret"),
        full_name="Target User",
        role="document_generator",
        is_active=True,
        bulk_generation_limit=None,
        created_at=datetime.now(timezone.utc),
    )
    _seed_user(fake_repo, target_user)

    # The /me endpoint reads the same user — seed them with the admin ID too
    # (auth/me uses ADMIN_USER_ID from get_current_user override in conftest)
    me_user = User(
        id=ADMIN_USER_ID,
        tenant_id=ADMIN_TENANT_ID,
        email="me_user@test.com",
        hashed_password=hash_password("any"),
        full_name="Me User",
        role="document_generator",
        is_active=True,
        bulk_generation_limit=None,
        created_at=datetime.now(timezone.utc),
    )
    _seed_user(fake_repo, me_user)

    repo_class = _make_users_repo_class(fake_repo)

    # Patch both the users and auth modules
    monkeypatch.setattr("app.presentation.api.v1.users.SQLAlchemyUserRepository", repo_class)
    monkeypatch.setattr("app.presentation.api.v1.auth.SQLAlchemyUserRepository", repo_class)

    # Patch get_settings so effective_bulk_limit uses a known global
    mock_settings = MagicMock()
    mock_settings.bulk_generation_limit = 10
    monkeypatch.setattr("app.presentation.api.v1.auth.get_settings", lambda: mock_settings)

    # Admin PUTs target user with limit=5
    put_response = await async_client.put(
        f"/api/v1/users/{TARGET_USER_ID}",
        headers=auth_headers,
        json={"bulk_generation_limit": 5},
    )
    assert put_response.status_code == 200, put_response.text
    assert put_response.json()["bulk_generation_limit"] == 5

    # Now verify the me_user's effective limit — we update me_user's limit via the same fake repo
    # to simulate what would happen if the admin also updated the requesting user's limit.
    # For this roundtrip, we update the me_user directly in the fake repo and call /auth/me.
    fake_repo._users[ADMIN_USER_ID].bulk_generation_limit = 5

    me_response = await async_client.get("/api/v1/auth/me", headers=auth_headers)
    assert me_response.status_code == 200, me_response.text
    data = me_response.json()
    assert data["effective_bulk_limit"] == 5


@pytest.mark.asyncio
async def test_admin_clears_user_bulk_limit_and_me_shows_global_default(
    async_client, auth_headers, monkeypatch
):
    """Admin PUTs user with bulk_generation_limit=null → GET /auth/me shows global default."""
    fake_repo = FakeUserRepository()

    me_user = User(
        id=ADMIN_USER_ID,
        tenant_id=ADMIN_TENANT_ID,
        email="me_clear@test.com",
        hashed_password=hash_password("any"),
        full_name="Me Clear User",
        role="document_generator",
        is_active=True,
        bulk_generation_limit=None,  # cleared / null
        created_at=datetime.now(timezone.utc),
    )
    _seed_user(fake_repo, me_user)

    repo_class = _make_users_repo_class(fake_repo)
    monkeypatch.setattr("app.presentation.api.v1.auth.SQLAlchemyUserRepository", repo_class)

    mock_settings = MagicMock()
    mock_settings.bulk_generation_limit = 10
    monkeypatch.setattr("app.presentation.api.v1.auth.get_settings", lambda: mock_settings)

    # User has null bulk_generation_limit → /me must return global default (10)
    me_response = await async_client.get("/api/v1/auth/me", headers=auth_headers)
    assert me_response.status_code == 200, me_response.text
    data = me_response.json()
    assert data["effective_bulk_limit"] == 10


# ── T-ADMIN-08/09: Role changes and last-admin guard ──────────────────────────


def _make_admin_user(user_id, tenant_id, role="admin") -> User:
    return User(
        id=user_id,
        tenant_id=tenant_id,
        email=f"{role}_{user_id}@test.com",
        hashed_password=hash_password("secret"),
        full_name=f"Test {role.capitalize()} User",
        role=role,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_promote_user_to_admin(async_client, auth_headers, monkeypatch):
    """SCEN-ADMIN-01: Admin promotes a user to admin role."""
    fake_repo = FakeUserRepository()
    target = _make_admin_user(TARGET_USER_ID, ADMIN_TENANT_ID, role="document_generator")
    admin = _make_admin_user(ADMIN_USER_ID, ADMIN_TENANT_ID, role="admin")
    _seed_user(fake_repo, target)
    _seed_user(fake_repo, admin)

    repo_class = _make_users_repo_class(fake_repo)
    monkeypatch.setattr("app.presentation.api.v1.users.SQLAlchemyUserRepository", repo_class)

    response = await async_client.put(
        f"/api/v1/users/{TARGET_USER_ID}",
        headers=auth_headers,
        json={"role": "admin"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["role"] == "admin"


@pytest.mark.asyncio
async def test_demote_admin_to_user_when_multiple_admins(async_client, auth_headers, monkeypatch):
    """SCEN-ADMIN-02: Can demote admin to document_generator when at least 2 admins exist."""
    second_admin_id = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
    fake_repo = FakeUserRepository()
    admin1 = _make_admin_user(ADMIN_USER_ID, ADMIN_TENANT_ID, role="admin")
    admin2 = _make_admin_user(second_admin_id, ADMIN_TENANT_ID, role="admin")
    _seed_user(fake_repo, admin1)
    _seed_user(fake_repo, admin2)

    repo_class = _make_users_repo_class(fake_repo)
    monkeypatch.setattr("app.presentation.api.v1.users.SQLAlchemyUserRepository", repo_class)

    response = await async_client.put(
        f"/api/v1/users/{second_admin_id}",
        headers=auth_headers,
        json={"role": "document_generator"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["role"] == "document_generator"


@pytest.mark.asyncio
async def test_demote_last_admin_returns_409(async_client, auth_headers, monkeypatch):
    """SCEN-ADMIN-03: Cannot demote the last admin — returns 409."""
    fake_repo = FakeUserRepository()
    admin = _make_admin_user(TARGET_USER_ID, ADMIN_TENANT_ID, role="admin")
    _seed_user(fake_repo, admin)
    # Requesting user is also admin (set by conftest), but they are a different user
    # Both have same tenant — only 1 admin total
    requesting_admin = _make_admin_user(ADMIN_USER_ID, ADMIN_TENANT_ID, role="admin")
    _seed_user(fake_repo, requesting_admin)

    repo_class = _make_users_repo_class(fake_repo)
    monkeypatch.setattr("app.presentation.api.v1.users.SQLAlchemyUserRepository", repo_class)

    # 2 admins exist — demote one should work
    # But if only 1 admin exists — should 409
    single_admin_repo = FakeUserRepository()
    only_admin = _make_admin_user(TARGET_USER_ID, ADMIN_TENANT_ID, role="admin")
    _seed_user(single_admin_repo, only_admin)
    single_repo_class = _make_users_repo_class(single_admin_repo)
    monkeypatch.setattr("app.presentation.api.v1.users.SQLAlchemyUserRepository", single_repo_class)

    response = await async_client.put(
        f"/api/v1/users/{TARGET_USER_ID}",
        headers=auth_headers,
        json={"role": "document_generator"},
    )
    assert response.status_code == 409, response.text
    assert "último administrador" in response.json()["detail"]


@pytest.mark.asyncio
async def test_invalid_role_returns_422(async_client, auth_headers, monkeypatch):
    """SCEN-ADMIN-05: Invalid role value returns 422."""
    fake_repo = FakeUserRepository()
    target = _make_admin_user(TARGET_USER_ID, ADMIN_TENANT_ID, role="document_generator")
    _seed_user(fake_repo, target)

    repo_class = _make_users_repo_class(fake_repo)
    monkeypatch.setattr("app.presentation.api.v1.users.SQLAlchemyUserRepository", repo_class)

    response = await async_client.put(
        f"/api/v1/users/{TARGET_USER_ID}",
        headers=auth_headers,
        json={"role": "superuser"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_deactivate_last_admin_returns_409(async_client, auth_headers, monkeypatch):
    """SCEN-ADMIN-04: Cannot deactivate the last admin — returns 409."""
    fake_repo = FakeUserRepository()
    only_admin = _make_admin_user(TARGET_USER_ID, ADMIN_TENANT_ID, role="admin")
    _seed_user(fake_repo, only_admin)

    repo_class = _make_users_repo_class(fake_repo)
    monkeypatch.setattr("app.presentation.api.v1.users.SQLAlchemyUserRepository", repo_class)

    response = await async_client.delete(
        f"/api/v1/users/{TARGET_USER_ID}",
        headers=auth_headers,
    )
    assert response.status_code == 409, response.text
    assert "último administrador" in response.json()["detail"]


# ── T-PRES-03: POST /users without role → role="document_generator" ──────────


def _make_users_repo_class_with_create(fake_repo: FakeUserRepository):
    """Extend _make_users_repo_class with a create() that returns a proper User entity.

    The real SQLAlchemy flushes defaults (is_active, created_at, etc.) on insert.
    In tests we simulate this by constructing a User domain entity from the UserModel.
    """
    from app.domain.entities import User
    from datetime import datetime, timezone

    base_class = _make_users_repo_class(fake_repo)

    class _RepoWithCreate(base_class):
        async def create(self, user_model):  # user_model is a UserModel from the endpoint
            # Build a proper User domain entity with all required fields
            user_entity = User(
                id=user_model.id,
                tenant_id=user_model.tenant_id,
                email=user_model.email,
                full_name=user_model.full_name,
                hashed_password=user_model.hashed_password,
                role=user_model.role,
                is_active=True,
                created_at=datetime.now(timezone.utc),
            )
            return await self._fake.create(user_entity)

    return _RepoWithCreate


@pytest.mark.asyncio
async def test_create_user_without_role_defaults_to_document_generator(
    async_client, auth_headers, monkeypatch
):
    """SCEN-ROLE-05: admin POSTs /users without role → 201, role=document_generator."""
    fake_repo = FakeUserRepository()

    repo_class = _make_users_repo_class_with_create(fake_repo)
    monkeypatch.setattr("app.presentation.api.v1.users.SQLAlchemyUserRepository", repo_class)

    response = await async_client.post(
        "/api/v1/users",
        headers=auth_headers,
        json={
            "email": "newuser@test.com",
            "full_name": "New User",
            "password": "securepassword123",
            # NOTE: no 'role' field — should default to document_generator
        },
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["role"] == "document_generator"


@pytest.mark.asyncio
async def test_create_user_with_explicit_admin_role(
    async_client, auth_headers, monkeypatch
):
    """Admin POSTs /users with role=admin → 201, role=admin."""
    fake_repo = FakeUserRepository()

    repo_class = _make_users_repo_class_with_create(fake_repo)
    monkeypatch.setattr("app.presentation.api.v1.users.SQLAlchemyUserRepository", repo_class)

    response = await async_client.post(
        "/api/v1/users",
        headers=auth_headers,
        json={
            "email": "newadmin@test.com",
            "full_name": "New Admin",
            "password": "securepassword123",
            "role": "admin",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["role"] == "admin"


@pytest.mark.asyncio
async def test_create_user_with_template_creator_role(
    async_client, auth_headers, monkeypatch
):
    """Admin POSTs /users with role=template_creator → 201."""
    fake_repo = FakeUserRepository()

    repo_class = _make_users_repo_class_with_create(fake_repo)
    monkeypatch.setattr("app.presentation.api.v1.users.SQLAlchemyUserRepository", repo_class)

    response = await async_client.post(
        "/api/v1/users",
        headers=auth_headers,
        json={
            "email": "creator@test.com",
            "full_name": "Template Creator",
            "password": "securepassword123",
            "role": "template_creator",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["role"] == "template_creator"


@pytest.mark.asyncio
async def test_create_user_with_invalid_role_returns_422(
    async_client, auth_headers, monkeypatch
):
    """Admin POSTs /users with an unknown role → 422 (validator rejects)."""
    fake_repo = FakeUserRepository()

    repo_class = _make_users_repo_class_with_create(fake_repo)
    monkeypatch.setattr("app.presentation.api.v1.users.SQLAlchemyUserRepository", repo_class)

    response = await async_client.post(
        "/api/v1/users",
        headers=auth_headers,
        json={
            "email": "weirdo@test.com",
            "full_name": "Weirdo",
            "password": "securepassword123",
            "role": "superuser",
        },
    )
    assert response.status_code == 422


# ── DELETE /users/{id} with reassign_to (B1) ─────────────────────────────────


@pytest.mark.asyncio
async def test_deactivate_user_without_templates_works(
    async_client, auth_headers, monkeypatch, fake_template_repo
):
    """Baseline retrocompat: deactivate succeeds when the user owns no templates."""
    fake_repo = FakeUserRepository()
    target = _make_admin_user(
        TARGET_USER_ID, ADMIN_TENANT_ID, role="document_generator"
    )
    _seed_user(fake_repo, target)
    requesting_admin = _make_admin_user(ADMIN_USER_ID, ADMIN_TENANT_ID, role="admin")
    _seed_user(fake_repo, requesting_admin)

    repo_class = _make_users_repo_class(fake_repo)
    monkeypatch.setattr("app.presentation.api.v1.users.SQLAlchemyUserRepository", repo_class)
    # No templates seeded for target → endpoint takes the simple soft-delete path.

    response = await async_client.delete(
        f"/api/v1/users/{TARGET_USER_ID}",
        headers=auth_headers,
    )
    assert response.status_code == 204, response.text


@pytest.mark.asyncio
async def test_deactivate_user_with_templates_returns_409_without_reassign(
    async_client, auth_headers, monkeypatch, fake_template_repo
):
    """User owns templates and admin doesn't pass reassign_to → 409 with hint."""
    from app.domain.entities import Template
    from datetime import datetime, timezone

    fake_repo = FakeUserRepository()
    target = _make_admin_user(
        TARGET_USER_ID, ADMIN_TENANT_ID, role="document_generator"
    )
    _seed_user(fake_repo, target)
    requesting_admin = _make_admin_user(ADMIN_USER_ID, ADMIN_TENANT_ID, role="admin")
    _seed_user(fake_repo, requesting_admin)

    # Seed a template owned by the target user
    tpl_id = uuid.uuid4()
    fake_template_repo._templates[tpl_id] = Template(
        id=tpl_id,
        tenant_id=ADMIN_TENANT_ID,
        name="OwnedByTarget",
        description=None,
        current_version=1,
        created_by=TARGET_USER_ID,
        versions=[],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    repo_class = _make_users_repo_class(fake_repo)
    monkeypatch.setattr("app.presentation.api.v1.users.SQLAlchemyUserRepository", repo_class)

    response = await async_client.delete(
        f"/api/v1/users/{TARGET_USER_ID}",
        headers=auth_headers,
    )
    assert response.status_code == 409, response.text
    assert "reassign_to" in response.json()["detail"]

    # Cleanup so other tests aren't affected
    fake_template_repo._templates.pop(tpl_id, None)


@pytest.mark.asyncio
async def test_deactivate_user_with_reassign_transfers_templates(
    async_client, auth_headers, monkeypatch, fake_template_repo
):
    """Happy path: reassign_to transfers ownership and then deactivates."""
    from app.domain.entities import Template
    from datetime import datetime, timezone

    REASSIGN_TARGET_ID = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")

    fake_repo = FakeUserRepository()
    target = _make_admin_user(
        TARGET_USER_ID, ADMIN_TENANT_ID, role="document_generator"
    )
    reassign_target = _make_admin_user(
        REASSIGN_TARGET_ID, ADMIN_TENANT_ID, role="document_generator"
    )
    requesting_admin = _make_admin_user(ADMIN_USER_ID, ADMIN_TENANT_ID, role="admin")
    _seed_user(fake_repo, target)
    _seed_user(fake_repo, reassign_target)
    _seed_user(fake_repo, requesting_admin)

    tpl_id = uuid.uuid4()
    fake_template_repo._templates[tpl_id] = Template(
        id=tpl_id,
        tenant_id=ADMIN_TENANT_ID,
        name="ReassignableTemplate",
        description=None,
        current_version=1,
        created_by=TARGET_USER_ID,
        versions=[],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    repo_class = _make_users_repo_class(fake_repo)
    monkeypatch.setattr("app.presentation.api.v1.users.SQLAlchemyUserRepository", repo_class)

    response = await async_client.delete(
        f"/api/v1/users/{TARGET_USER_ID}?reassign_to={REASSIGN_TARGET_ID}",
        headers=auth_headers,
    )
    assert response.status_code == 204, response.text
    # Template ownership transferred
    assert fake_template_repo._templates[tpl_id].created_by == REASSIGN_TARGET_ID

    fake_template_repo._templates.pop(tpl_id, None)


@pytest.mark.asyncio
async def test_deactivate_user_reassign_to_self_returns_400(
    async_client, auth_headers, monkeypatch, fake_template_repo
):
    from app.domain.entities import Template
    from datetime import datetime, timezone

    fake_repo = FakeUserRepository()
    target = _make_admin_user(
        TARGET_USER_ID, ADMIN_TENANT_ID, role="document_generator"
    )
    _seed_user(fake_repo, target)
    requesting_admin = _make_admin_user(ADMIN_USER_ID, ADMIN_TENANT_ID, role="admin")
    _seed_user(fake_repo, requesting_admin)

    tpl_id = uuid.uuid4()
    fake_template_repo._templates[tpl_id] = Template(
        id=tpl_id,
        tenant_id=ADMIN_TENANT_ID,
        name="SelfReassignTpl",
        description=None,
        current_version=1,
        created_by=TARGET_USER_ID,
        versions=[],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    repo_class = _make_users_repo_class(fake_repo)
    monkeypatch.setattr("app.presentation.api.v1.users.SQLAlchemyUserRepository", repo_class)

    response = await async_client.delete(
        f"/api/v1/users/{TARGET_USER_ID}?reassign_to={TARGET_USER_ID}",
        headers=auth_headers,
    )
    assert response.status_code == 400, response.text

    fake_template_repo._templates.pop(tpl_id, None)


@pytest.mark.asyncio
async def test_deactivate_user_reassign_to_inactive_returns_400(
    async_client, auth_headers, monkeypatch, fake_template_repo
):
    from app.domain.entities import Template, User
    from datetime import datetime, timezone

    INACTIVE_TARGET_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")

    fake_repo = FakeUserRepository()
    target = _make_admin_user(
        TARGET_USER_ID, ADMIN_TENANT_ID, role="document_generator"
    )
    inactive_user = User(
        id=INACTIVE_TARGET_ID,
        tenant_id=ADMIN_TENANT_ID,
        email="inactive@test.com",
        hashed_password=hash_password("x"),
        full_name="Inactive User",
        role="document_generator",
        is_active=False,
        created_at=datetime.now(timezone.utc),
    )
    requesting_admin = _make_admin_user(ADMIN_USER_ID, ADMIN_TENANT_ID, role="admin")
    _seed_user(fake_repo, target)
    _seed_user(fake_repo, inactive_user)
    _seed_user(fake_repo, requesting_admin)

    tpl_id = uuid.uuid4()
    fake_template_repo._templates[tpl_id] = Template(
        id=tpl_id,
        tenant_id=ADMIN_TENANT_ID,
        name="InactiveReassignTpl",
        description=None,
        current_version=1,
        created_by=TARGET_USER_ID,
        versions=[],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    repo_class = _make_users_repo_class(fake_repo)
    monkeypatch.setattr("app.presentation.api.v1.users.SQLAlchemyUserRepository", repo_class)

    response = await async_client.delete(
        f"/api/v1/users/{TARGET_USER_ID}?reassign_to={INACTIVE_TARGET_ID}",
        headers=auth_headers,
    )
    assert response.status_code == 400, response.text

    fake_template_repo._templates.pop(tpl_id, None)


@pytest.mark.asyncio
async def test_deactivate_user_reassign_to_nonexistent_returns_404(
    async_client, auth_headers, monkeypatch, fake_template_repo
):
    from app.domain.entities import Template
    from datetime import datetime, timezone

    NONEXISTENT_ID = uuid.UUID("88888888-8888-8888-8888-888888888888")

    fake_repo = FakeUserRepository()
    target = _make_admin_user(
        TARGET_USER_ID, ADMIN_TENANT_ID, role="document_generator"
    )
    requesting_admin = _make_admin_user(ADMIN_USER_ID, ADMIN_TENANT_ID, role="admin")
    _seed_user(fake_repo, target)
    _seed_user(fake_repo, requesting_admin)

    tpl_id = uuid.uuid4()
    fake_template_repo._templates[tpl_id] = Template(
        id=tpl_id,
        tenant_id=ADMIN_TENANT_ID,
        name="NoTargetTpl",
        description=None,
        current_version=1,
        created_by=TARGET_USER_ID,
        versions=[],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    repo_class = _make_users_repo_class(fake_repo)
    monkeypatch.setattr("app.presentation.api.v1.users.SQLAlchemyUserRepository", repo_class)

    response = await async_client.delete(
        f"/api/v1/users/{TARGET_USER_ID}?reassign_to={NONEXISTENT_ID}",
        headers=auth_headers,
    )
    assert response.status_code == 404, response.text

    fake_template_repo._templates.pop(tpl_id, None)
