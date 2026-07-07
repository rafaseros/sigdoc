"""Integration tests — POST /api/v1/documents/preview.

Ephemeral true-fidelity document preview: renders the docx template with
the CURRENT (possibly partial) variable values and returns the converted
PDF bytes directly. Nothing is persisted.

Uses the fakes wired in integration conftest. Before each test that calls
preview, we seed a TemplateVersion into the shared FakeTemplateRepository
and the corresponding template bytes into FakeStorageService.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.domain.entities import Template, TemplateVersion
from tests.fakes import FakeStorageService, FakeTemplateRepository

# ── Helpers ───────────────────────────────────────────────────────────────────

CONFTEST_TENANT_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
CONFTEST_USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


def seed_template_version(
    fake_template_repo: FakeTemplateRepository,
    fake_storage: FakeStorageService,
    variables: list[str] | None = None,
    owner_id: uuid.UUID | None = None,
) -> str:
    """Seed a Template + TemplateVersion in the fake repo and fake storage.

    Returns the version_id as a string.
    """
    if variables is None:
        variables = ["name", "company", "date"]

    if owner_id is None:
        owner_id = CONFTEST_USER_ID

    template_id = uuid.uuid4()
    version_id = uuid.uuid4()
    minio_path = f"{CONFTEST_TENANT_ID}/{template_id}/v1/template.docx"
    now = datetime.now(timezone.utc)

    version = TemplateVersion(
        id=version_id,
        tenant_id=CONFTEST_TENANT_ID,
        template_id=template_id,
        version=1,
        minio_path=minio_path,
        variables=variables,
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
    fake_storage.files[("templates", minio_path)] = b"fake-docx-bytes"

    return str(version_id)


# ── Unauthenticated requests ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_preview_without_auth_returns_401(async_client, app):
    from app.presentation.middleware.tenant import get_current_user

    original = app.dependency_overrides.pop(get_current_user, None)
    try:
        response = await async_client.post(
            "/api/v1/documents/preview",
            json={"template_version_id": str(uuid.uuid4()), "variables": {}},
        )
        assert response.status_code == 401
    finally:
        if original is not None:
            app.dependency_overrides[get_current_user] = original


# ── Authenticated preview ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_preview_with_valid_version_returns_200_pdf(
    async_client, auth_headers, fake_template_repo, fake_storage
):
    version_id = seed_template_version(fake_template_repo, fake_storage)

    response = await async_client.post(
        "/api/v1/documents/preview",
        headers=auth_headers,
        json={
            "template_version_id": version_id,
            "variables": {"name": "Alice", "company": "ACME", "date": "2025-01-01"},
        },
    )

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    assert len(response.content) > 0


@pytest.mark.asyncio
async def test_preview_accepts_partial_variables(
    async_client, auth_headers, fake_template_repo, fake_storage
):
    """Only 1 of 3 template variables provided — still returns 200 with a PDF.

    Missing variables render as blanks (docxtpl default Jinja2 Undefined) —
    no 422/400 expected for incompleteness.
    """
    version_id = seed_template_version(
        fake_template_repo, fake_storage, variables=["name", "company", "date"]
    )

    response = await async_client.post(
        "/api/v1/documents/preview",
        headers=auth_headers,
        json={
            "template_version_id": version_id,
            "variables": {"name": "Alice"},
        },
    )

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"


@pytest.mark.asyncio
async def test_preview_with_unknown_version_returns_404(async_client, auth_headers):
    response = await async_client.post(
        "/api/v1/documents/preview",
        headers=auth_headers,
        json={
            "template_version_id": str(uuid.uuid4()),
            "variables": {"name": "Alice"},
        },
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_preview_with_extra_field_returns_422(
    async_client, auth_headers, fake_template_repo, fake_storage
):
    """extra="forbid": any unknown field in the body → 422."""
    version_id = seed_template_version(fake_template_repo, fake_storage)

    response = await async_client.post(
        "/api/v1/documents/preview",
        headers=auth_headers,
        json={
            "template_version_id": version_id,
            "variables": {"name": "Alice"},
            "output_format": "pdf",  # unknown field — MUST be rejected
        },
    )

    assert response.status_code == 422, response.text


@pytest.mark.asyncio
async def test_preview_does_not_persist_a_document(
    async_client, auth_headers, fake_template_repo, fake_storage, fake_document_repo
):
    """After a successful preview, no Document row is created (nothing persisted)."""
    version_id = seed_template_version(fake_template_repo, fake_storage)
    documents_before = len(fake_document_repo._documents)

    response = await async_client.post(
        "/api/v1/documents/preview",
        headers=auth_headers,
        json={
            "template_version_id": version_id,
            "variables": {"name": "Alice", "company": "ACME", "date": "2025-01-01"},
        },
    )

    assert response.status_code == 200, response.text
    assert len(fake_document_repo._documents) == documents_before


# ── Rate limiting ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_preview_returns_429_with_low_tier_limit(
    async_client, auth_headers, fake_template_repo, fake_storage
):
    """The /preview route is decorated with the preview rate limit — hitting
    a low limit returns 429, proving the decorator is wired in."""
    from tests.integration.test_rate_limit import (
        _patch_limiter_dynamic_limit,
        _restore_limiter_providers,
    )
    from app.presentation.middleware.rate_limit import limiter

    version_id = seed_template_version(fake_template_repo, fake_storage)

    patched = _patch_limiter_dynamic_limit(limiter, "preview_document", lambda: "2/minute")
    try:
        for i in range(2):
            r = await async_client.post(
                "/api/v1/documents/preview",
                headers=auth_headers,
                json={
                    "template_version_id": version_id,
                    "variables": {"name": "Alice"},
                },
            )
            assert r.status_code == 200, f"Request {i + 1}: {r.status_code} — {r.text}"

        r = await async_client.post(
            "/api/v1/documents/preview",
            headers=auth_headers,
            json={
                "template_version_id": version_id,
                "variables": {"name": "Alice"},
            },
        )
        assert r.status_code == 429, f"Expected 429, got {r.status_code}"
    finally:
        _restore_limiter_providers(patched)
