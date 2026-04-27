"""Integration tests — template endpoint role gates (T-PRES-06..10).

Tests for:
  SCEN-TMP-02: document_generator blocked from POST /templates/upload → 403
  SCEN-TMP-03: template_creator can POST /templates/upload → 201
  SCEN-TMP-04: admin can POST /templates/upload → 201
  SCEN-TMP-05: document_generator blocked from POST /templates/{id}/versions → 403
  SCEN-TMP-06: template_creator can POST /templates/{id}/versions (owned) → 201
  SCEN-TMP-07: document_generator generates from shared template → 201
  SCEN-TMP-08: document_generator blocked from non-shared template → 403

All role gates tested here are enforced by `require_template_manager` dependency.
Document generation (SCEN-TMP-07/08) is NOT gated — enforcement is at repository
access layer (TemplateAccessDeniedError from _check_access).
"""

from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone

import pytest

from app.domain.entities import Template, TemplateVersion
from app.presentation.middleware.tenant import CurrentUser, get_current_user

# ── Stable IDs ────────────────────────────────────────────────────────────────

CONFTEST_USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
CONFTEST_TENANT_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

DOC_GEN_USER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
TMPL_CREATOR_USER_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")


# ── Helper: build a valid .docx upload payload ────────────────────────────────

def _docx_upload_files():
    return {
        "file": (
            "template.docx",
            io.BytesIO(b"fake-docx-bytes"),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    }


# ── Helper: override current_user for a specific role ────────────────────────

def _user_override(user_id: uuid.UUID, role: str) -> CurrentUser:
    return CurrentUser(
        user_id=user_id,
        tenant_id=CONFTEST_TENANT_ID,
        role=role,
    )


def _seed_template(fake_template_repo, owner_id: uuid.UUID) -> uuid.UUID:
    """Directly seed a template owned by owner_id. Returns template_id."""
    template_id = uuid.uuid4()
    version_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    version = TemplateVersion(
        id=version_id,
        tenant_id=CONFTEST_TENANT_ID,
        template_id=template_id,
        version=1,
        minio_path=f"{CONFTEST_TENANT_ID}/{template_id}/v1/template.docx",
        variables=["name"],
        created_at=now,
    )
    template = Template(
        id=template_id,
        tenant_id=CONFTEST_TENANT_ID,
        name=f"TestTemplate-{template_id}",
        description=None,
        current_version=1,
        created_by=owner_id,
        versions=[version],
        created_at=now,
        updated_at=now,
    )
    fake_template_repo._templates[template_id] = template
    fake_template_repo._versions[version_id] = version
    return template_id


# ── Group B: Upload endpoint gates ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_document_generator_cannot_upload_template(
    async_client, app, auth_headers, monkeypatch, fake_template_engine
):
    """SCEN-TMP-02: document_generator calls POST /templates/upload → 403."""
    monkeypatch.setattr(
        "app.presentation.api.v1.templates.get_template_engine",
        lambda: fake_template_engine,
    )
    fake_template_engine.variables_to_return = ["name"]

    user = _user_override(DOC_GEN_USER_ID, "document_generator")

    async def override():
        return user

    original = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = override
    try:
        response = await async_client.post(
            "/api/v1/templates/upload",
            headers=auth_headers,
            data={"name": "Blocked Template"},
            files=_docx_upload_files(),
        )
        assert response.status_code == 403, response.text
    finally:
        if original is not None:
            app.dependency_overrides[get_current_user] = original
        else:
            app.dependency_overrides.pop(get_current_user, None)
        fake_template_engine.variables_to_return = []


@pytest.mark.asyncio
async def test_template_creator_can_upload_template(
    async_client, app, auth_headers, monkeypatch, fake_template_engine
):
    """SCEN-TMP-03: template_creator calls POST /templates/upload → 201."""
    monkeypatch.setattr(
        "app.presentation.api.v1.templates.get_template_engine",
        lambda: fake_template_engine,
    )
    fake_template_engine.variables_to_return = ["name"]

    user = _user_override(TMPL_CREATOR_USER_ID, "template_creator")

    async def override():
        return user

    original = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = override
    try:
        response = await async_client.post(
            "/api/v1/templates/upload",
            headers=auth_headers,
            data={"name": "Creator Template"},
            files=_docx_upload_files(),
        )
        assert response.status_code == 201, response.text
    finally:
        if original is not None:
            app.dependency_overrides[get_current_user] = original
        else:
            app.dependency_overrides.pop(get_current_user, None)
        fake_template_engine.variables_to_return = []


@pytest.mark.asyncio
async def test_admin_can_upload_template(
    async_client, app, auth_headers, monkeypatch, fake_template_engine
):
    """SCEN-TMP-04: admin calls POST /templates/upload → 201."""
    monkeypatch.setattr(
        "app.presentation.api.v1.templates.get_template_engine",
        lambda: fake_template_engine,
    )
    fake_template_engine.variables_to_return = ["name"]

    # Default conftest user is admin; use auth_headers directly (no override needed)
    response = await async_client.post(
        "/api/v1/templates/upload",
        headers=auth_headers,
        data={"name": "Admin Template"},
        files=_docx_upload_files(),
    )
    assert response.status_code == 201, response.text
    fake_template_engine.variables_to_return = []


@pytest.mark.asyncio
async def test_document_generator_cannot_upload_new_version(
    async_client, app, auth_headers, fake_template_repo, monkeypatch, fake_template_engine
):
    """SCEN-TMP-05: document_generator calls POST /templates/{id}/versions → 403."""
    # Seed a template shared with the doc_gen user so the access check doesn't
    # fire before the role gate; we want to confirm the role gate fires first.
    tpl_id = _seed_template(fake_template_repo, CONFTEST_USER_ID)
    await fake_template_repo.add_share(
        template_id=tpl_id,
        user_id=DOC_GEN_USER_ID,
        tenant_id=CONFTEST_TENANT_ID,
        shared_by=CONFTEST_USER_ID,
    )

    monkeypatch.setattr(
        "app.presentation.api.v1.templates.get_template_engine",
        lambda: fake_template_engine,
    )
    fake_template_engine.variables_to_return = ["name"]

    user = _user_override(DOC_GEN_USER_ID, "document_generator")

    async def override():
        return user

    original = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = override
    try:
        response = await async_client.post(
            f"/api/v1/templates/{tpl_id}/versions",
            headers=auth_headers,
            files=_docx_upload_files(),
        )
        assert response.status_code == 403, response.text
    finally:
        if original is not None:
            app.dependency_overrides[get_current_user] = original
        else:
            app.dependency_overrides.pop(get_current_user, None)
        fake_template_engine.variables_to_return = []


@pytest.mark.asyncio
async def test_template_creator_can_upload_new_version_on_own_template(
    async_client, app, auth_headers, fake_template_repo, monkeypatch, fake_template_engine
):
    """SCEN-TMP-06: template_creator calls POST /templates/{id}/versions (own) → 201."""
    # Seed a template OWNED by the template_creator user
    tpl_id = _seed_template(fake_template_repo, TMPL_CREATOR_USER_ID)

    monkeypatch.setattr(
        "app.presentation.api.v1.templates.get_template_engine",
        lambda: fake_template_engine,
    )
    fake_template_engine.variables_to_return = ["name"]

    user = _user_override(TMPL_CREATOR_USER_ID, "template_creator")

    async def override():
        return user

    original = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = override
    try:
        response = await async_client.post(
            f"/api/v1/templates/{tpl_id}/versions",
            headers=auth_headers,
            files=_docx_upload_files(),
        )
        assert response.status_code == 201, response.text
    finally:
        if original is not None:
            app.dependency_overrides[get_current_user] = original
        else:
            app.dependency_overrides.pop(get_current_user, None)
        fake_template_engine.variables_to_return = []


# ── Group E: Document generation (ungated — REQ-TMP-05) ──────────────────────


@pytest.mark.asyncio
async def test_document_generator_generates_from_shared_template(
    async_client, app, auth_headers, fake_template_repo, fake_storage
):
    """SCEN-TMP-07: document_generator generates from shared template → 201.

    No role gate on the generate endpoint. Access is enforced at the repository
    layer: if a share record exists, the call succeeds.
    """
    from app.domain.entities import TemplateVersion

    template_id = uuid.uuid4()
    version_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    version = TemplateVersion(
        id=version_id,
        tenant_id=CONFTEST_TENANT_ID,
        template_id=template_id,
        version=1,
        minio_path=f"{CONFTEST_TENANT_ID}/{template_id}/v1/template.docx",
        variables=["name", "date"],
        created_at=now,
    )
    template = Template(
        id=template_id,
        tenant_id=CONFTEST_TENANT_ID,
        name="SharedForGenerate",
        description=None,
        current_version=1,
        created_by=CONFTEST_USER_ID,
        versions=[version],
        created_at=now,
        updated_at=now,
    )
    fake_template_repo._templates[template_id] = template
    fake_template_repo._versions[version_id] = version

    # Seed template bytes in storage (needed for document generation)
    minio_path = f"{CONFTEST_TENANT_ID}/{template_id}/v1/template.docx"
    fake_storage.files[("templates", minio_path)] = b"fake-docx-for-generate"

    # Share template with doc gen user
    await fake_template_repo.add_share(
        template_id=template_id,
        user_id=DOC_GEN_USER_ID,
        tenant_id=CONFTEST_TENANT_ID,
        shared_by=CONFTEST_USER_ID,
    )

    user = _user_override(DOC_GEN_USER_ID, "document_generator")

    async def override():
        return user

    original = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = override
    try:
        response = await async_client.post(
            "/api/v1/documents/generate",
            headers=auth_headers,
            json={
                "template_version_id": str(version_id),
                "variables": {"name": "Test User", "date": "2024-01-01"},
            },
        )
        assert response.status_code == 201, response.text
    finally:
        if original is not None:
            app.dependency_overrides[get_current_user] = original
        else:
            app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_document_generator_blocked_from_non_shared_template(
    async_client, app, auth_headers, fake_template_repo
):
    """SCEN-TMP-08: document_generator generates from non-shared template → 403.

    No role gate on the generate endpoint. The 403 comes from
    TemplateAccessDeniedError raised by _check_access in template_service.py
    when no share record exists for the requesting user.
    """
    # Seed a template owned by CONFTEST_USER — NOT shared with DOC_GEN_USER
    template_id = uuid.uuid4()
    version_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    version = TemplateVersion(
        id=version_id,
        tenant_id=CONFTEST_TENANT_ID,
        template_id=template_id,
        version=1,
        minio_path=f"{CONFTEST_TENANT_ID}/{template_id}/v1/template.docx",
        variables=["name"],
        created_at=now,
    )
    template = Template(
        id=template_id,
        tenant_id=CONFTEST_TENANT_ID,
        name="PrivateForGenerate",
        description=None,
        current_version=1,
        created_by=CONFTEST_USER_ID,
        versions=[version],
        created_at=now,
        updated_at=now,
    )
    fake_template_repo._templates[template_id] = template
    fake_template_repo._versions[version_id] = version
    # NOTE: no add_share call — template is NOT shared with doc gen user

    user = _user_override(DOC_GEN_USER_ID, "document_generator")

    async def override():
        return user

    original = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = override
    try:
        response = await async_client.post(
            "/api/v1/documents/generate",
            headers=auth_headers,
            json={
                "template_version_id": str(version_id),
                "variables": {"name": "Test User"},
            },
        )
        assert response.status_code == 403, response.text
    finally:
        if original is not None:
            app.dependency_overrides[get_current_user] = original
        else:
            app.dependency_overrides.pop(get_current_user, None)
