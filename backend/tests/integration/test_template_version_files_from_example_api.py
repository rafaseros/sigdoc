"""Integration tests — attach a related file created FROM AN EXAMPLE.

Route under test:
- POST /api/v1/templates/{tid}/versions/{vid}/files/from-example
  (multipart `file`, form `label`, form `mappings` JSON string)

Contract: the union of the plain attach contract (201 file shape, 409
duplicate label / non-current version, 403 non-owner, role gate) and the
/templates/from-example contract (422 mapping variants — string detail,
{message, errors}, {message, missing_texts} — and 400 bad/empty file).

Follows the style of test_template_version_files_api.py: fakes wired in the
integration conftest, per-test get_current_user overrides. FakeTemplateEngine
models documents as UTF-8 text bytes so the full pipeline
(rewrite → extract → store → union → respond) is exercised end to end.
"""

from __future__ import annotations

import io
import json
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
EXAMPLE_TEXT = "Recibo de JUAN PEREZ por 100 Bs."
EXAMPLE_BYTES = EXAMPLE_TEXT.encode("utf-8")
MAPPINGS = [
    {"text": "JUAN PEREZ", "variable": "name"},  # reuses the version variable
    {"text": "100", "variable": "monto"},  # new variable
]
REWRITTEN_TEXT = "Recibo de {{ name }} por {{ monto }} Bs."


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
        name=name or f"FromExampleFiles-{template_id}",
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
        variables=["name"],
        file_size=10,
        position=0,
        created_at=datetime.now(timezone.utc),
    )
    version.files.append(file)
    fake_template_repo._version_files[(version_id, file_id)] = file
    fake_storage.files[("templates", minio_path)] = b"Recibo {{ name }}"
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


def _payload(
    label: str = "Recibo de pago",
    mappings: str | None = None,
    file_bytes: bytes = EXAMPLE_BYTES,
):
    return {
        "data": {
            "label": label,
            "mappings": mappings if mappings is not None else json.dumps(MAPPINGS),
        },
        "files": {"file": ("recibo.docx", io.BytesIO(file_bytes), DOCX_MIME)},
    }


def _url(tpl_id: uuid.UUID, ver_id: uuid.UUID) -> str:
    return f"/api/v1/templates/{tpl_id}/versions/{ver_id}/files/from-example"


# ── Happy path ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_owner_attaches_from_example_returns_201_with_file_shape(
    async_client, app, auth_headers, fake_template_repo, fake_storage
):
    tpl_id, ver_id = _seed_template(fake_template_repo, fake_storage)

    with _OverrideUser(app, _user(OWNER_USER_ID, "template_creator")):
        payload = _payload()
        response = await async_client.post(
            _url(tpl_id, ver_id),
            headers=auth_headers,
            data=payload["data"],
            files=payload["files"],
        )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["label"] == "Recibo de pago"
    assert body["variables"] == ["name", "monto"]
    assert body["position"] == 0
    assert body["file_size"] == len(REWRITTEN_TEXT.encode("utf-8"))
    assert "id" in body and "created_at" in body

    # The stored object is the REWRITTEN document, not the original example
    stored_key = (
        "templates",
        f"{CONFTEST_TENANT_ID}/{tpl_id}/v1/files/{body['id']}.docx",
    )
    stored_text = fake_storage.files[stored_key].decode("utf-8")
    assert "{{ name }}" in stored_text
    assert "{{ monto }}" in stored_text
    assert "JUAN PEREZ" not in stored_text


@pytest.mark.asyncio
async def test_attach_from_example_unions_variables_in_template_detail(
    async_client, app, auth_headers, fake_template_repo, fake_storage
):
    tpl_id, ver_id = _seed_template(fake_template_repo, fake_storage)

    with _OverrideUser(app, _user(OWNER_USER_ID, "template_creator")):
        payload = _payload()
        attach_resp = await async_client.post(
            _url(tpl_id, ver_id),
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
    # Reused "name" is NOT duplicated; new "monto" is appended.
    assert data["variables"] == ["name", "monto"]
    version = data["versions"][0]
    assert version["variables"] == ["name", "monto"]
    meta_names = [m["name"] for m in version["variables_meta"]]
    assert meta_names == ["name", "monto"]
    assert len(version["files"]) == 1
    assert version["files"][0]["label"] == "Recibo de pago"
    assert version["files"][0]["variables"] == ["name", "monto"]


# ── 422 mapping variants ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_missing_text_returns_422_with_missing_list(
    async_client, app, auth_headers, fake_template_repo, fake_storage
):
    tpl_id, ver_id = _seed_template(fake_template_repo, fake_storage)

    with _OverrideUser(app, _user(OWNER_USER_ID, "template_creator")):
        payload = _payload(
            mappings=json.dumps(
                [
                    {"text": "NO ESTA EN EL DOCUMENTO", "variable": "uno"},
                    {"text": "JUAN PEREZ", "variable": "name"},
                ]
            )
        )
        response = await async_client.post(
            _url(tpl_id, ver_id),
            headers=auth_headers,
            data=payload["data"],
            files=payload["files"],
        )

    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert detail["missing_texts"] == ["NO ESTA EN EL DOCUMENTO"]
    assert "NO ESTA EN EL DOCUMENTO" in detail["message"]


@pytest.mark.asyncio
async def test_invalid_json_mappings_returns_422_string_detail(
    async_client, app, auth_headers, fake_template_repo, fake_storage
):
    tpl_id, ver_id = _seed_template(fake_template_repo, fake_storage)

    with _OverrideUser(app, _user(OWNER_USER_ID, "template_creator")):
        payload = _payload(mappings="not-a-json")
        response = await async_client.post(
            _url(tpl_id, ver_id),
            headers=auth_headers,
            data=payload["data"],
            files=payload["files"],
        )

    assert response.status_code == 422, response.text
    assert isinstance(response.json()["detail"], str)


@pytest.mark.asyncio
async def test_bad_variable_name_returns_422_with_errors(
    async_client, app, auth_headers, fake_template_repo, fake_storage
):
    tpl_id, ver_id = _seed_template(fake_template_repo, fake_storage)

    with _OverrideUser(app, _user(OWNER_USER_ID, "template_creator")):
        payload = _payload(
            mappings=json.dumps([{"text": "JUAN PEREZ", "variable": "ClientName"}])
        )
        response = await async_client.post(
            _url(tpl_id, ver_id),
            headers=auth_headers,
            data=payload["data"],
            files=payload["files"],
        )

    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert detail["message"] == "Mappings inválidos"
    assert len(detail["errors"]) >= 1


@pytest.mark.asyncio
async def test_empty_mappings_returns_422(
    async_client, app, auth_headers, fake_template_repo, fake_storage
):
    tpl_id, ver_id = _seed_template(fake_template_repo, fake_storage)

    with _OverrideUser(app, _user(OWNER_USER_ID, "template_creator")):
        payload = _payload(mappings="[]")
        response = await async_client.post(
            _url(tpl_id, ver_id),
            headers=auth_headers,
            data=payload["data"],
            files=payload["files"],
        )

    assert response.status_code == 422, response.text


@pytest.mark.asyncio
async def test_blank_label_returns_422(
    async_client, app, auth_headers, fake_template_repo, fake_storage
):
    tpl_id, ver_id = _seed_template(fake_template_repo, fake_storage)

    with _OverrideUser(app, _user(OWNER_USER_ID, "template_creator")):
        payload = _payload(label="   ")
        response = await async_client.post(
            _url(tpl_id, ver_id),
            headers=auth_headers,
            data=payload["data"],
            files=payload["files"],
        )

    assert response.status_code == 422, response.text


# ── 409s ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_duplicate_label_returns_409(
    async_client, app, auth_headers, fake_template_repo, fake_storage
):
    tpl_id, ver_id = _seed_template(fake_template_repo, fake_storage)
    _seed_related_file(fake_template_repo, fake_storage, tpl_id, ver_id)

    with _OverrideUser(app, _user(OWNER_USER_ID, "template_creator")):
        payload = _payload(label="Recibo de pago")
        response = await async_client.post(
            _url(tpl_id, ver_id),
            headers=auth_headers,
            data=payload["data"],
            files=payload["files"],
        )

    assert response.status_code == 409, response.text
    assert "etiqueta" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_non_current_version_returns_409(
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
        payload = _payload()
        response = await async_client.post(
            _url(tpl_id, v1_id),
            headers=auth_headers,
            data=payload["data"],
            files=payload["files"],
        )

    assert response.status_code == 409, response.text


# ── Access matrix ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unrelated_template_creator_returns_403(
    async_client, app, auth_headers, fake_template_repo, fake_storage
):
    tpl_id, ver_id = _seed_template(fake_template_repo, fake_storage)

    with _OverrideUser(app, _user(UNRELATED_USER_ID, "template_creator")):
        payload = _payload()
        response = await async_client.post(
            _url(tpl_id, ver_id),
            headers=auth_headers,
            data=payload["data"],
            files=payload["files"],
        )

    assert response.status_code == 403, response.text


@pytest.mark.asyncio
async def test_shared_document_generator_returns_403(
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
        payload = _payload()
        response = await async_client.post(
            _url(tpl_id, ver_id),
            headers=auth_headers,
            data=payload["data"],
            files=payload["files"],
        )

    assert response.status_code == 403, response.text


@pytest.mark.asyncio
async def test_admin_can_attach_from_example_to_foreign_template(
    async_client, auth_headers, fake_template_repo, fake_storage
):
    # Conftest default user is admin — no override needed.
    tpl_id, ver_id = _seed_template(fake_template_repo, fake_storage)

    payload = _payload()
    response = await async_client.post(
        _url(tpl_id, ver_id),
        headers=auth_headers,
        data=payload["data"],
        files=payload["files"],
    )

    assert response.status_code == 201, response.text


# ── 404 / 400 ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unknown_version_returns_404(
    async_client, app, auth_headers, fake_template_repo, fake_storage
):
    tpl_id, _ = _seed_template(fake_template_repo, fake_storage)

    with _OverrideUser(app, _user(OWNER_USER_ID, "template_creator")):
        payload = _payload()
        response = await async_client.post(
            _url(tpl_id, uuid.uuid4()),
            headers=auth_headers,
            data=payload["data"],
            files=payload["files"],
        )

    assert response.status_code == 404, response.text


@pytest.mark.asyncio
async def test_empty_file_returns_400(
    async_client, app, auth_headers, fake_template_repo, fake_storage
):
    tpl_id, ver_id = _seed_template(fake_template_repo, fake_storage)

    with _OverrideUser(app, _user(OWNER_USER_ID, "template_creator")):
        payload = _payload(file_bytes=b"")
        response = await async_client.post(
            _url(tpl_id, ver_id),
            headers=auth_headers,
            data=payload["data"],
            files=payload["files"],
        )

    assert response.status_code == 400, response.text
