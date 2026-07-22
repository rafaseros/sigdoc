"""Integration tests — related files per template version (Tanda 3).

Routes under test:
- POST   /api/v1/templates/{tid}/versions/{vid}/files            (attach)
- DELETE /api/v1/templates/{tid}/versions/{vid}/files/{fid}      (detach)
- GET    /api/v1/templates/{tid}/versions/{vid}/files/{fid}/download
- GET    /api/v1/templates/{tid}/versions/{vid}/structure?file_id=
- POST   /api/v1/documents/generate (new {"documents": [...], "group_id"} shape)

Access matrix: attach/detach = owner-or-admin (role-gated by
require_template_manager first); download = owner-or-admin (raw stored .docx
is not available to shared users); structure = any template access.

Follows the style of test_template_version_download.py: fakes wired in the
integration conftest, per-test get_current_user overrides.
"""

from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone

import pytest

from app.domain.entities import Template, TemplateVersion, TemplateVersionFile
from app.presentation.middleware.tenant import CurrentUser, get_current_user

# ── Stable IDs ────────────────────────────────────────────────────────────────

CONFTEST_TENANT_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

OWNER_USER_ID = uuid.UUID("77777777-7777-7777-7777-777777777777")
SHARED_USER_ID = uuid.UUID("88888888-8888-8888-8888-888888888888")
UNRELATED_USER_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PRIMARY_BYTES = b"Contrato {{ name }}"
RECIBO_BYTES = b"Recibo {{ name }} {{ monto }}"


@pytest.fixture(autouse=True)
def _fake_engine_for_validation(monkeypatch, fake_template_engine):
    """The attach endpoint calls get_template_engine() directly (outside DI)
    for pre-upload validation — patch it to the shared fake, same pattern as
    test_templates_api.py."""
    monkeypatch.setattr(
        "app.presentation.api.v1.templates.get_template_engine",
        lambda: fake_template_engine,
    )


def _seed_template(
    fake_template_repo,
    fake_storage,
    owner_id: uuid.UUID = OWNER_USER_ID,
    *,
    name: str | None = None,
    version_number: int = 1,
) -> tuple[uuid.UUID, uuid.UUID]:
    """Seed a template + version in the fakes. Returns (template_id, version_id)."""
    template_id = uuid.uuid4()
    version_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    minio_path = f"{CONFTEST_TENANT_ID}/{template_id}/v{version_number}/template.docx"

    version = TemplateVersion(
        id=version_id,
        tenant_id=CONFTEST_TENANT_ID,
        template_id=template_id,
        version=version_number,
        minio_path=minio_path,
        variables=["name"],
        variables_meta=[{"name": "name", "contexts": []}],
        created_at=now,
    )
    template = Template(
        id=template_id,
        tenant_id=CONFTEST_TENANT_ID,
        name=name or f"FilesTemplate-{template_id}",
        description=None,
        current_version=version_number,
        created_by=owner_id,
        versions=[version],
        created_at=now,
        updated_at=now,
    )
    fake_template_repo._templates[template_id] = template
    fake_template_repo._versions[version_id] = version
    fake_storage.files[("templates", minio_path)] = PRIMARY_BYTES
    return template_id, version_id


def _seed_related_file(
    fake_template_repo,
    fake_storage,
    template_id: uuid.UUID,
    version_id: uuid.UUID,
    *,
    label: str = "Recibo de pago",
    file_bytes: bytes = RECIBO_BYTES,
    position: int = 0,
) -> TemplateVersionFile:
    """Seed a related file row + storage object directly in the fakes."""
    file_id = uuid.uuid4()
    version = fake_template_repo._versions[version_id]
    minio_path = (
        f"{CONFTEST_TENANT_ID}/{template_id}/v{version.version}/files/{file_id}.docx"
    )
    file = TemplateVersionFile(
        id=file_id,
        tenant_id=CONFTEST_TENANT_ID,
        version_id=version_id,
        label=label,
        minio_path=minio_path,
        variables=["name", "monto"],
        file_size=len(file_bytes),
        position=position,
        created_at=datetime.now(timezone.utc),
    )
    version.files.append(file)
    fake_template_repo._version_files[(version_id, file_id)] = file
    fake_storage.files[("templates", minio_path)] = file_bytes
    return file


def _user(user_id: uuid.UUID, role: str) -> CurrentUser:
    return CurrentUser(user_id=user_id, tenant_id=CONFTEST_TENANT_ID, role=role)


class _OverrideUser:
    """Context manager that swaps get_current_user for a specific user."""

    def __init__(self, app, user: CurrentUser):
        self._app = app
        self._user = user
        self._original = None

    def __enter__(self):
        async def override():
            return self._user

        self._original = self._app.dependency_overrides.get(get_current_user)
        self._app.dependency_overrides[get_current_user] = override
        return self

    def __exit__(self, *exc):
        if self._original is not None:
            self._app.dependency_overrides[get_current_user] = self._original
        else:
            self._app.dependency_overrides.pop(get_current_user, None)
        return False


def _attach_payload(label: str = "Recibo de pago", file_bytes: bytes = RECIBO_BYTES):
    return {
        "data": {"label": label},
        "files": {"file": ("recibo.docx", io.BytesIO(file_bytes), DOCX_MIME)},
    }


# ── Attach ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_owner_can_attach_file(
    async_client, app, auth_headers, fake_template_repo, fake_storage
):
    tpl_id, ver_id = _seed_template(fake_template_repo, fake_storage)

    with _OverrideUser(app, _user(OWNER_USER_ID, "template_creator")):
        payload = _attach_payload()
        response = await async_client.post(
            f"/api/v1/templates/{tpl_id}/versions/{ver_id}/files",
            headers=auth_headers,
            data=payload["data"],
            files=payload["files"],
        )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["label"] == "Recibo de pago"
    assert body["variables"] == ["name", "monto"]
    assert body["position"] == 0
    assert body["file_size"] == len(RECIBO_BYTES)
    assert "id" in body and "created_at" in body


@pytest.mark.asyncio
async def test_attach_unions_variables_and_exposes_files_in_template_detail(
    async_client, app, auth_headers, fake_template_repo, fake_storage
):
    tpl_id, ver_id = _seed_template(fake_template_repo, fake_storage)

    with _OverrideUser(app, _user(OWNER_USER_ID, "template_creator")):
        payload = _attach_payload()
        attach_resp = await async_client.post(
            f"/api/v1/templates/{tpl_id}/versions/{ver_id}/files",
            headers=auth_headers,
            data=payload["data"],
            files=payload["files"],
        )
        assert attach_resp.status_code == 201, attach_resp.text

        detail = await async_client.get(
            f"/api/v1/templates/{tpl_id}", headers=auth_headers
        )

    assert detail.status_code == 200, detail.text
    data = detail.json()
    # The version's variables are now the union
    assert data["variables"] == ["name", "monto"]
    version = data["versions"][0]
    assert version["variables"] == ["name", "monto"]
    assert len(version["files"]) == 1
    assert version["files"][0]["label"] == "Recibo de pago"
    assert version["files"][0]["variables"] == ["name", "monto"]


@pytest.mark.asyncio
async def test_attach_duplicate_label_returns_409(
    async_client, app, auth_headers, fake_template_repo, fake_storage
):
    tpl_id, ver_id = _seed_template(fake_template_repo, fake_storage)
    _seed_related_file(fake_template_repo, fake_storage, tpl_id, ver_id)

    with _OverrideUser(app, _user(OWNER_USER_ID, "template_creator")):
        payload = _attach_payload(label="Recibo de pago")
        response = await async_client.post(
            f"/api/v1/templates/{tpl_id}/versions/{ver_id}/files",
            headers=auth_headers,
            data=payload["data"],
            files=payload["files"],
        )

    assert response.status_code == 409, response.text


@pytest.mark.asyncio
async def test_attach_to_non_current_version_returns_409(
    async_client, app, auth_headers, fake_template_repo, fake_storage
):
    tpl_id, v1_id = _seed_template(fake_template_repo, fake_storage)
    # Make v2 current; v1 remains seeded
    template = fake_template_repo._templates[tpl_id]
    now = datetime.now(timezone.utc)
    v2 = TemplateVersion(
        id=uuid.uuid4(),
        tenant_id=CONFTEST_TENANT_ID,
        template_id=tpl_id,
        version=2,
        minio_path=f"{CONFTEST_TENANT_ID}/{tpl_id}/v2/template.docx",
        variables=["name"],
        created_at=now,
    )
    fake_template_repo._versions[v2.id] = v2
    template.versions.append(v2)
    template.current_version = 2

    with _OverrideUser(app, _user(OWNER_USER_ID, "template_creator")):
        payload = _attach_payload()
        response = await async_client.post(
            f"/api/v1/templates/{tpl_id}/versions/{v1_id}/files",
            headers=auth_headers,
            data=payload["data"],
            files=payload["files"],
        )

    assert response.status_code == 409, response.text


@pytest.mark.asyncio
async def test_unrelated_template_creator_cannot_attach(
    async_client, app, auth_headers, fake_template_repo, fake_storage
):
    tpl_id, ver_id = _seed_template(fake_template_repo, fake_storage)

    with _OverrideUser(app, _user(UNRELATED_USER_ID, "template_creator")):
        payload = _attach_payload()
        response = await async_client.post(
            f"/api/v1/templates/{tpl_id}/versions/{ver_id}/files",
            headers=auth_headers,
            data=payload["data"],
            files=payload["files"],
        )

    assert response.status_code == 403, response.text


@pytest.mark.asyncio
async def test_shared_document_generator_cannot_attach(
    async_client, app, auth_headers, fake_template_repo, fake_storage
):
    """Shared users can generate, but managing related files is role-gated."""
    tpl_id, ver_id = _seed_template(fake_template_repo, fake_storage)
    await fake_template_repo.add_share(
        template_id=tpl_id,
        user_id=SHARED_USER_ID,
        tenant_id=CONFTEST_TENANT_ID,
        shared_by=OWNER_USER_ID,
    )

    with _OverrideUser(app, _user(SHARED_USER_ID, "document_generator")):
        payload = _attach_payload()
        response = await async_client.post(
            f"/api/v1/templates/{tpl_id}/versions/{ver_id}/files",
            headers=auth_headers,
            data=payload["data"],
            files=payload["files"],
        )

    assert response.status_code == 403, response.text


@pytest.mark.asyncio
async def test_admin_can_attach_to_foreign_template(
    async_client, auth_headers, fake_template_repo, fake_storage
):
    # Conftest default user is admin — no override needed.
    tpl_id, ver_id = _seed_template(fake_template_repo, fake_storage)

    payload = _attach_payload()
    response = await async_client.post(
        f"/api/v1/templates/{tpl_id}/versions/{ver_id}/files",
        headers=auth_headers,
        data=payload["data"],
        files=payload["files"],
    )

    assert response.status_code == 201, response.text


@pytest.mark.asyncio
async def test_attach_unknown_version_returns_404(
    async_client, app, auth_headers, fake_template_repo, fake_storage
):
    tpl_id, _ = _seed_template(fake_template_repo, fake_storage)

    with _OverrideUser(app, _user(OWNER_USER_ID, "template_creator")):
        payload = _attach_payload()
        response = await async_client.post(
            f"/api/v1/templates/{tpl_id}/versions/{uuid.uuid4()}/files",
            headers=auth_headers,
            data=payload["data"],
            files=payload["files"],
        )

    assert response.status_code == 404, response.text


@pytest.mark.asyncio
async def test_attach_blank_label_returns_422(
    async_client, app, auth_headers, fake_template_repo, fake_storage
):
    tpl_id, ver_id = _seed_template(fake_template_repo, fake_storage)

    with _OverrideUser(app, _user(OWNER_USER_ID, "template_creator")):
        payload = _attach_payload(label="   ")
        response = await async_client.post(
            f"/api/v1/templates/{tpl_id}/versions/{ver_id}/files",
            headers=auth_headers,
            data=payload["data"],
            files=payload["files"],
        )

    assert response.status_code == 422, response.text


# ── Detach ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_owner_can_detach_file(
    async_client, app, auth_headers, fake_template_repo, fake_storage
):
    tpl_id, ver_id = _seed_template(fake_template_repo, fake_storage)
    file = _seed_related_file(fake_template_repo, fake_storage, tpl_id, ver_id)

    with _OverrideUser(app, _user(OWNER_USER_ID, "template_creator")):
        response = await async_client.delete(
            f"/api/v1/templates/{tpl_id}/versions/{ver_id}/files/{file.id}",
            headers=auth_headers,
        )

    assert response.status_code == 204, response.text
    assert (ver_id, file.id) not in fake_template_repo._version_files
    assert ("templates", file.minio_path) not in fake_storage.files
    # Union recomputed: monto (only in the detached file) is gone
    version = fake_template_repo._versions[ver_id]
    assert version.variables == ["name"]


@pytest.mark.asyncio
async def test_detach_unknown_file_returns_404(
    async_client, app, auth_headers, fake_template_repo, fake_storage
):
    tpl_id, ver_id = _seed_template(fake_template_repo, fake_storage)

    with _OverrideUser(app, _user(OWNER_USER_ID, "template_creator")):
        response = await async_client.delete(
            f"/api/v1/templates/{tpl_id}/versions/{ver_id}/files/{uuid.uuid4()}",
            headers=auth_headers,
        )

    assert response.status_code == 404, response.text


@pytest.mark.asyncio
async def test_unrelated_user_cannot_detach(
    async_client, app, auth_headers, fake_template_repo, fake_storage
):
    tpl_id, ver_id = _seed_template(fake_template_repo, fake_storage)
    file = _seed_related_file(fake_template_repo, fake_storage, tpl_id, ver_id)

    with _OverrideUser(app, _user(UNRELATED_USER_ID, "template_creator")):
        response = await async_client.delete(
            f"/api/v1/templates/{tpl_id}/versions/{ver_id}/files/{file.id}",
            headers=auth_headers,
        )

    assert response.status_code == 403, response.text


# ── Download ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_owner_can_download_related_file(
    async_client, app, auth_headers, fake_template_repo, fake_storage
):
    tpl_id, ver_id = _seed_template(
        fake_template_repo, fake_storage, name="Contrato Marco"
    )
    file = _seed_related_file(fake_template_repo, fake_storage, tpl_id, ver_id)

    with _OverrideUser(app, _user(OWNER_USER_ID, "template_creator")):
        response = await async_client.get(
            f"/api/v1/templates/{tpl_id}/versions/{ver_id}/files/{file.id}/download",
            headers=auth_headers,
        )

    assert response.status_code == 200, response.text
    assert response.content == RECIBO_BYTES
    assert response.headers["content-type"].startswith(DOCX_MIME)
    disposition = response.headers["content-disposition"]
    assert "attachment" in disposition
    assert "Recibo de pago_v1.docx" in disposition


@pytest.mark.asyncio
async def test_shared_user_blocked_from_related_file_download(
    async_client, app, auth_headers, fake_template_repo, fake_storage
):
    """Shared users can generate documents but must NOT download the raw
    stored .docx of a related file — owner-or-admin only."""
    tpl_id, ver_id = _seed_template(fake_template_repo, fake_storage)
    file = _seed_related_file(fake_template_repo, fake_storage, tpl_id, ver_id)
    await fake_template_repo.add_share(
        template_id=tpl_id,
        user_id=SHARED_USER_ID,
        tenant_id=CONFTEST_TENANT_ID,
        shared_by=OWNER_USER_ID,
    )

    with _OverrideUser(app, _user(SHARED_USER_ID, "document_generator")):
        response = await async_client.get(
            f"/api/v1/templates/{tpl_id}/versions/{ver_id}/files/{file.id}/download",
            headers=auth_headers,
        )

    assert response.status_code == 403, response.text


@pytest.mark.asyncio
async def test_admin_can_download_related_file(
    async_client, app, auth_headers, fake_template_repo, fake_storage
):
    # Conftest default user is admin — no override needed.
    tpl_id, ver_id = _seed_template(fake_template_repo, fake_storage)
    file = _seed_related_file(fake_template_repo, fake_storage, tpl_id, ver_id)

    response = await async_client.get(
        f"/api/v1/templates/{tpl_id}/versions/{ver_id}/files/{file.id}/download",
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    assert response.content == RECIBO_BYTES


@pytest.mark.asyncio
async def test_unrelated_user_blocked_from_related_file_download(
    async_client, app, auth_headers, fake_template_repo, fake_storage
):
    tpl_id, ver_id = _seed_template(fake_template_repo, fake_storage)
    file = _seed_related_file(fake_template_repo, fake_storage, tpl_id, ver_id)

    with _OverrideUser(app, _user(UNRELATED_USER_ID, "user")):
        response = await async_client.get(
            f"/api/v1/templates/{tpl_id}/versions/{ver_id}/files/{file.id}/download",
            headers=auth_headers,
        )

    assert response.status_code == 403, response.text


@pytest.mark.asyncio
async def test_download_file_of_another_version_returns_404(
    async_client, app, auth_headers, fake_template_repo, fake_storage
):
    tpl_id, ver_a = _seed_template(fake_template_repo, fake_storage)
    _, ver_b = _seed_template(fake_template_repo, fake_storage)
    file_b = _seed_related_file(
        fake_template_repo, fake_storage, tpl_id, ver_b
    )

    with _OverrideUser(app, _user(OWNER_USER_ID, "template_creator")):
        response = await async_client.get(
            f"/api/v1/templates/{tpl_id}/versions/{ver_a}/files/{file_b.id}/download",
            headers=auth_headers,
        )

    assert response.status_code == 404, response.text


# ── Structure with file_id ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_structure_with_file_id_returns_200(
    async_client, app, auth_headers, fake_template_repo, fake_storage
):
    tpl_id, ver_id = _seed_template(fake_template_repo, fake_storage)
    file = _seed_related_file(fake_template_repo, fake_storage, tpl_id, ver_id)

    with _OverrideUser(app, _user(OWNER_USER_ID, "template_creator")):
        response = await async_client.get(
            f"/api/v1/templates/{tpl_id}/versions/{ver_id}/structure?file_id={file.id}",
            headers=auth_headers,
        )

    assert response.status_code == 200, response.text
    data = response.json()
    assert set(data) == {"headers", "body", "footers"}


@pytest.mark.asyncio
async def test_structure_with_unknown_file_id_returns_404(
    async_client, app, auth_headers, fake_template_repo, fake_storage
):
    tpl_id, ver_id = _seed_template(fake_template_repo, fake_storage)

    with _OverrideUser(app, _user(OWNER_USER_ID, "template_creator")):
        response = await async_client.get(
            f"/api/v1/templates/{tpl_id}/versions/{ver_id}/structure?file_id={uuid.uuid4()}",
            headers=auth_headers,
        )

    assert response.status_code == 404, response.text


# ── Generate — multi-file response shape ──────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_multifile_returns_documents_and_group(
    async_client, auth_headers, fake_template_repo, fake_storage
):
    tpl_id, ver_id = _seed_template(
        fake_template_repo, fake_storage, owner_id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    )
    _seed_related_file(fake_template_repo, fake_storage, tpl_id, ver_id)

    response = await async_client.post(
        "/api/v1/documents/generate",
        headers=auth_headers,
        json={
            "template_version_id": str(ver_id),
            "variables": {"name": "Alice", "monto": "100"},
        },
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["group_id"] is not None
    docs = data["documents"]
    assert len(docs) == 2
    # Primary first, related file with the label injected before the extension
    assert docs[0]["docx_file_name"] == "Alice.docx"
    assert docs[1]["docx_file_name"] == "Alice_Recibo_de_pago.docx"
    for doc in docs:
        assert doc["group_id"] == data["group_id"]
        assert doc["status"] == "completed"
        assert doc["download_url"] == f"/documents/{doc['id']}/download"


@pytest.mark.asyncio
async def test_preview_with_file_id_returns_pdf(
    async_client, auth_headers, fake_template_repo, fake_storage
):
    tpl_id, ver_id = _seed_template(
        fake_template_repo, fake_storage, owner_id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    )
    file = _seed_related_file(fake_template_repo, fake_storage, tpl_id, ver_id)

    response = await async_client.post(
        "/api/v1/documents/preview",
        headers=auth_headers,
        json={
            "template_version_id": str(ver_id),
            "variables": {"name": "Alice"},
            "file_id": str(file.id),
        },
    )

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/pdf")


@pytest.mark.asyncio
async def test_preview_with_unknown_file_id_returns_404(
    async_client, auth_headers, fake_template_repo, fake_storage
):
    tpl_id, ver_id = _seed_template(
        fake_template_repo, fake_storage, owner_id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    )

    response = await async_client.post(
        "/api/v1/documents/preview",
        headers=auth_headers,
        json={
            "template_version_id": str(ver_id),
            "variables": {"name": "Alice"},
            "file_id": str(uuid.uuid4()),
        },
    )

    assert response.status_code == 404, response.text
