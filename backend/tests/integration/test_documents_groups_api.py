"""Integration tests — grouped generated documents + combined ZIP download.

Feature #4, Phase A. Covers:
- GET /documents/groups: exact response shape, standalone docs, pagination by
  group unit, and REQ-OWN-DOCS scoping (own / admin-all / template-owner)
  mirroring the flat list.
- GET /documents/groups/{group_id}/download: owner/admin ZIP with all members,
  non-admin pdf OK, non-admin docx → 403, unknown/foreign group → 404.

All tests use in-memory fakes (session-scoped in conftest). To stay isolated
from documents seeded by sibling test modules, list assertions scope by a
UNIQUE non-admin user id or a UNIQUE template id.
"""

from __future__ import annotations

import io
import uuid
import zipfile
from datetime import datetime, timedelta, timezone

import pytest

from app.domain.entities import Document, Template, TemplateVersion
from app.presentation.middleware.tenant import CurrentUser, get_current_user

TENANT_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
ADMIN_USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


# ── seeding helpers ──────────────────────────────────────────────────────────


def _seed_group(
    repo,
    storage,
    *,
    created_by,
    tenant_id=TENANT_ID,
    template_version_id=None,
    labels=("Recibo", "Factura"),
    template_name="Contrato Laboral",
    base_time=None,
    with_pdf=True,
):
    """Insert a primary + related documents sharing one group_id.

    Returns (group_id, [documents primary-first]).
    """
    template_version_id = template_version_id or uuid.uuid4()
    base_time = base_time or datetime.now(timezone.utc)
    group_id = uuid.uuid4()
    docs = []
    for pos, label in enumerate([None, *labels]):
        doc_id = uuid.uuid4()
        docx_fn = f"doc_{pos}.docx" if label is None else f"doc_{pos}_{label}.docx"
        pdf_fn = docx_fn[:-5] + ".pdf"
        docx_path = f"{tenant_id}/{group_id}/{docx_fn}"
        pdf_path = f"{tenant_id}/{group_id}/{pdf_fn}"
        doc = Document(
            id=doc_id,
            tenant_id=tenant_id,
            template_version_id=template_version_id,
            docx_file_name=docx_fn,
            docx_minio_path=docx_path,
            pdf_file_name=pdf_fn if with_pdf else None,
            pdf_minio_path=pdf_path if with_pdf else None,
            generation_type="single",
            group_id=group_id,
            related_label=label,
            group_position=pos,
            variables_snapshot={"name": "Alice"},
            created_by=created_by,
            status="completed",
            created_at=base_time + timedelta(seconds=pos),
            template_id=uuid.uuid4(),
            template_name=template_name,
            template_version=1,
        )
        repo._documents[doc_id] = doc
        storage.files[("documents", docx_path)] = b"fake-docx"
        if with_pdf:
            storage.files[("documents", pdf_path)] = b"fake-pdf"
        docs.append(doc)
    return group_id, docs


def _seed_standalone(repo, storage, *, created_by, tenant_id=TENANT_ID, base_time=None):
    base_time = base_time or datetime.now(timezone.utc)
    doc_id = uuid.uuid4()
    docx_path = f"{tenant_id}/{doc_id}/solo.docx"
    doc = Document(
        id=doc_id,
        tenant_id=tenant_id,
        template_version_id=uuid.uuid4(),
        docx_file_name="solo.docx",
        docx_minio_path=docx_path,
        pdf_file_name="solo.pdf",
        pdf_minio_path=f"{tenant_id}/{doc_id}/solo.pdf",
        generation_type="single",
        group_id=None,
        related_label=None,
        group_position=0,
        variables_snapshot={"name": "Solo"},
        created_by=created_by,
        status="completed",
        created_at=base_time,
        template_id=uuid.uuid4(),
        template_name="Solo Template",
        template_version=1,
    )
    repo._documents[doc_id] = doc
    storage.files[("documents", docx_path)] = b"fake-docx"
    return doc


def _override_user(app, user: CurrentUser):
    async def _override():
        return user

    original = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = _override
    return original


def _restore_user(app, original):
    if original is not None:
        app.dependency_overrides[get_current_user] = original
    else:
        app.dependency_overrides.pop(get_current_user, None)


# ═══════════════════════════════════════════════════════════════════════════
# GET /documents/groups — shape, standalone, pagination
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_groups_list_shape(
    async_client, app, auth_headers, fake_document_repo, fake_storage
):
    me = uuid.uuid4()
    group_id, docs = _seed_group(
        fake_document_repo, fake_storage, created_by=me, labels=["Recibo", "Factura"]
    )

    user = CurrentUser(user_id=me, tenant_id=TENANT_ID, role="user")
    original = _override_user(app, user)
    try:
        resp = await async_client.get("/api/v1/documents/groups", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert set(body) == {"items", "total", "page", "size"}
        assert body["total"] == 1
        assert body["page"] == 1 and body["size"] == 20
        assert len(body["items"]) == 1

        item = body["items"][0]
        assert set(item) == {"group_id", "primary", "related"}
        assert item["group_id"] == str(group_id)
        assert item["primary"]["related_label"] is None
        assert item["primary"]["group_id"] == str(group_id)
        assert [r["related_label"] for r in item["related"]] == ["Recibo", "Factura"]
    finally:
        _restore_user(app, original)


@pytest.mark.asyncio
async def test_groups_list_standalone_group_id_null_related_empty(
    async_client, app, auth_headers, fake_document_repo, fake_storage
):
    me = uuid.uuid4()
    doc = _seed_standalone(fake_document_repo, fake_storage, created_by=me)

    user = CurrentUser(user_id=me, tenant_id=TENANT_ID, role="user")
    original = _override_user(app, user)
    try:
        resp = await async_client.get("/api/v1/documents/groups", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total"] == 1
        item = body["items"][0]
        assert item["group_id"] is None
        assert item["related"] == []
        assert item["primary"]["id"] == str(doc.id)
    finally:
        _restore_user(app, original)


@pytest.mark.asyncio
async def test_groups_list_pagination_by_group_unit(
    async_client, app, auth_headers, fake_document_repo, fake_storage
):
    me = uuid.uuid4()
    base = datetime.now(timezone.utc)
    _seed_group(
        fake_document_repo, fake_storage, created_by=me, labels=["Recibo"], base_time=base
    )
    _seed_standalone(
        fake_document_repo, fake_storage, created_by=me, base_time=base + timedelta(minutes=1)
    )
    _seed_standalone(
        fake_document_repo, fake_storage, created_by=me, base_time=base + timedelta(minutes=2)
    )

    user = CurrentUser(user_id=me, tenant_id=TENANT_ID, role="user")
    original = _override_user(app, user)
    try:
        p1 = (await async_client.get(
            "/api/v1/documents/groups?page=1&size=2", headers=auth_headers
        )).json()
        p2 = (await async_client.get(
            "/api/v1/documents/groups?page=2&size=2", headers=auth_headers
        )).json()
        assert p1["total"] == 3 and p2["total"] == 3
        assert len(p1["items"]) == 2
        assert len(p2["items"]) == 1
    finally:
        _restore_user(app, original)


@pytest.mark.asyncio
async def test_groups_non_admin_sees_only_own(
    async_client, app, auth_headers, fake_document_repo, fake_storage
):
    me = uuid.uuid4()
    other = uuid.uuid4()
    _seed_group(fake_document_repo, fake_storage, created_by=me, labels=["Recibo"])
    _seed_group(fake_document_repo, fake_storage, created_by=other, labels=["Recibo"])

    user = CurrentUser(user_id=me, tenant_id=TENANT_ID, role="user")
    original = _override_user(app, user)
    try:
        body = (await async_client.get(
            "/api/v1/documents/groups", headers=auth_headers
        )).json()
        assert body["total"] == 1
    finally:
        _restore_user(app, original)


@pytest.mark.asyncio
async def test_groups_template_owner_sees_all_for_template(
    async_client, app, auth_headers, fake_document_repo, fake_template_repo, fake_storage
):
    """REQ-OWN-DOCS: a non-admin who OWNS the template sees every group of that
    template (bypasses created_by), mirroring the flat list."""
    owner = uuid.uuid4()
    other = uuid.uuid4()
    template_id = uuid.uuid4()
    version_id = uuid.uuid4()

    # Seed the template owned by `owner` so get_owner_id resolves.
    now = datetime.now(timezone.utc)
    version = TemplateVersion(
        id=version_id, tenant_id=TENANT_ID, template_id=template_id, version=1,
        minio_path=f"{TENANT_ID}/{template_id}/v1/t.docx", variables=["name"], created_at=now,
    )
    fake_template_repo._templates[template_id] = Template(
        id=template_id, tenant_id=TENANT_ID, name="Owned", description=None,
        current_version=1, created_by=owner, versions=[version], created_at=now, updated_at=now,
    )
    fake_template_repo._versions[version_id] = version
    # Map version → template so the groups list template filter works.
    fake_document_repo.register_template_version(version_id, template_id)

    # Two groups under this template: one by owner, one by another user.
    _seed_group(
        fake_document_repo, fake_storage, created_by=owner,
        template_version_id=version_id, labels=["Recibo"],
    )
    _seed_group(
        fake_document_repo, fake_storage, created_by=other,
        template_version_id=version_id, labels=["Recibo"],
    )

    user = CurrentUser(user_id=owner, tenant_id=TENANT_ID, role="user")
    original = _override_user(app, user)
    try:
        body = (await async_client.get(
            f"/api/v1/documents/groups?template_id={template_id}", headers=auth_headers
        )).json()
        # Owner sees BOTH groups of the template (own + other's).
        assert body["total"] == 2
    finally:
        _restore_user(app, original)


# ═══════════════════════════════════════════════════════════════════════════
# GET /documents/groups/{group_id}/download — combined ZIP
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_group_zip_admin_pdf_all_members(
    async_client, auth_headers, fake_document_repo, fake_storage
):
    """Admin (conftest default) downloads a group ZIP (pdf) → all 3 members."""
    group_id, docs = _seed_group(
        fake_document_repo, fake_storage, created_by=ADMIN_USER_ID, labels=["Recibo", "Factura"]
    )
    resp = await async_client.get(
        f"/api/v1/documents/groups/{group_id}/download?format=pdf", headers=auth_headers
    )
    assert resp.status_code == 200, resp.text
    assert "zip" in resp.headers.get("content-type", "").lower()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        names = zf.namelist()
    assert len(names) == 3
    assert all(n.endswith(".pdf") for n in names)
    # Filename must be {sanitized_template_name}_paquete.zip
    assert "paquete.zip" in resp.headers.get("content-disposition", "").lower()


@pytest.mark.asyncio
async def test_group_zip_admin_docx_all_members(
    async_client, auth_headers, fake_document_repo, fake_storage
):
    group_id, docs = _seed_group(
        fake_document_repo, fake_storage, created_by=ADMIN_USER_ID, labels=["Recibo"]
    )
    resp = await async_client.get(
        f"/api/v1/documents/groups/{group_id}/download?format=docx", headers=auth_headers
    )
    assert resp.status_code == 200, resp.text
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        names = zf.namelist()
    assert len(names) == 2
    assert all(n.endswith(".docx") for n in names)


@pytest.mark.asyncio
async def test_group_zip_non_admin_owner_pdf_ok(
    async_client, app, auth_headers, fake_document_repo, fake_storage
):
    me = uuid.uuid4()
    group_id, _ = _seed_group(
        fake_document_repo, fake_storage, created_by=me, labels=["Recibo"]
    )
    user = CurrentUser(user_id=me, tenant_id=TENANT_ID, role="user")
    original = _override_user(app, user)
    try:
        resp = await async_client.get(
            f"/api/v1/documents/groups/{group_id}/download?format=pdf", headers=auth_headers
        )
        assert resp.status_code == 200, resp.text
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            assert len(zf.namelist()) == 2
    finally:
        _restore_user(app, original)


@pytest.mark.asyncio
async def test_group_zip_non_admin_docx_403(
    async_client, app, auth_headers, fake_document_repo, fake_storage
):
    me = uuid.uuid4()
    group_id, _ = _seed_group(
        fake_document_repo, fake_storage, created_by=me, labels=["Recibo"]
    )
    user = CurrentUser(user_id=me, tenant_id=TENANT_ID, role="user")
    original = _override_user(app, user)
    try:
        resp = await async_client.get(
            f"/api/v1/documents/groups/{group_id}/download?format=docx", headers=auth_headers
        )
        assert resp.status_code == 403, resp.text
    finally:
        _restore_user(app, original)


@pytest.mark.asyncio
async def test_group_zip_unknown_group_404(async_client, auth_headers):
    group_id = uuid.uuid4()
    resp = await async_client.get(
        f"/api/v1/documents/groups/{group_id}/download?format=pdf", headers=auth_headers
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_group_zip_foreign_group_404(
    async_client, app, auth_headers, fake_document_repo, fake_storage
):
    """A non-admin requesting another user's group → non-leaking 404."""
    other = uuid.uuid4()
    group_id, _ = _seed_group(
        fake_document_repo, fake_storage, created_by=other, labels=["Recibo"]
    )
    me = uuid.uuid4()
    user = CurrentUser(user_id=me, tenant_id=TENANT_ID, role="user")
    original = _override_user(app, user)
    try:
        resp = await async_client.get(
            f"/api/v1/documents/groups/{group_id}/download?format=pdf", headers=auth_headers
        )
        assert resp.status_code == 404, resp.text
    finally:
        _restore_user(app, original)
