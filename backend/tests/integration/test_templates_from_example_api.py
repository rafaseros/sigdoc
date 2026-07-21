"""Integration tests — template-from-example endpoints.

POST /api/v1/templates/analyze-example  — structure preview of an example docx
POST /api/v1/templates/from-example     — rewrite literals into placeholders
                                          and create a normal template v1

Uses the integration conftest fakes. FakeTemplateEngine models documents as
UTF-8 text bytes: apply_variable_mappings does string-level replacement and
extract_variables scans for {{ ... }} markers, so the full pipeline
(rewrite → extract → store → respond) is exercised end to end.
"""

from __future__ import annotations

import io
import json
import uuid

import pytest

from app.presentation.middleware.tenant import get_current_user

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

CONFTEST_TENANT_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

EXAMPLE_TEXT = "CONTRATO entre JUAN PEREZ y ACME SRL en la ciudad."


def _docx_file(content: bytes = EXAMPLE_TEXT.encode("utf-8"), name: str = "ejemplo.docx"):
    return {"file": (name, io.BytesIO(content), DOCX_MIME)}


# ── Auth gates ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_analyze_example_without_auth_returns_401(async_client, app):
    original = app.dependency_overrides.pop(get_current_user, None)
    try:
        response = await async_client.post(
            "/api/v1/templates/analyze-example", files=_docx_file()
        )
        assert response.status_code == 401
    finally:
        if original is not None:
            app.dependency_overrides[get_current_user] = original


@pytest.mark.asyncio
async def test_from_example_without_auth_returns_401(async_client, app):
    original = app.dependency_overrides.pop(get_current_user, None)
    try:
        response = await async_client.post(
            "/api/v1/templates/from-example",
            data={"name": "X", "mappings": "[]"},
            files=_docx_file(),
        )
        assert response.status_code == 401
    finally:
        if original is not None:
            app.dependency_overrides[get_current_user] = original


# ── analyze-example ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_analyze_example_returns_structure_for_doc_without_placeholders(
    async_client, auth_headers, fake_template_engine
):
    """A real filled document has NO placeholders: every span is plain text
    with variable=None. The endpoint returns {"structure": {...}}."""
    fake_template_engine.structure_to_return = {
        "headers": [],
        "body": [
            {
                "kind": "paragraph",
                "level": 0,
                "spans": [{"text": EXAMPLE_TEXT, "variable": None}],
            }
        ],
        "footers": [],
    }
    try:
        response = await async_client.post(
            "/api/v1/templates/analyze-example",
            headers=auth_headers,
            files=_docx_file(),
        )

        assert response.status_code == 200
        data = response.json()
        assert "structure" in data
        structure = data["structure"]
        assert structure["headers"] == []
        assert structure["footers"] == []
        assert len(structure["body"]) == 1
        node = structure["body"][0]
        assert node["kind"] == "paragraph"
        assert node["spans"] == [{"text": EXAMPLE_TEXT, "variable": None}]
    finally:
        fake_template_engine.structure_to_return = {
            "headers": [],
            "body": [],
            "footers": [],
        }


@pytest.mark.asyncio
async def test_analyze_example_rejects_non_docx(async_client, auth_headers):
    response = await async_client.post(
        "/api/v1/templates/analyze-example",
        headers=auth_headers,
        files={"file": ("notas.txt", io.BytesIO(b"plain text"), "text/plain")},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_analyze_example_rejects_empty_file(async_client, auth_headers):
    response = await async_client.post(
        "/api/v1/templates/analyze-example",
        headers=auth_headers,
        files=_docx_file(content=b""),
    )
    assert response.status_code == 400


# ── from-example: happy path ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_from_example_creates_template_with_mapped_variables(
    async_client, auth_headers, fake_storage
):
    mappings = [
        {"text": "JUAN PEREZ", "variable": "client_name"},
        {"text": "ACME SRL", "variable": "company"},
    ]

    response = await async_client.post(
        "/api/v1/templates/from-example",
        headers=auth_headers,
        data={
            "name": "Plantilla desde ejemplo",
            "description": "Generada desde un contrato real",
            "mappings": json.dumps(mappings),
        },
        files=_docx_file(),
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["name"] == "Plantilla desde ejemplo"
    assert data["description"] == "Generada desde un contrato real"
    assert data["version"] == 1
    assert set(data["variables"]) == {"client_name", "company"}
    assert "id" in data
    assert "created_at" in data

    # Stored v1 bytes are the REWRITTEN document, not the original example
    template_id = data["id"]
    stored = fake_storage.files[
        ("templates", f"{CONFTEST_TENANT_ID}/{template_id}/v1/template.docx")
    ]
    stored_text = stored.decode("utf-8")
    assert "{{ client_name }}" in stored_text
    assert "{{ company }}" in stored_text
    assert "JUAN PEREZ" not in stored_text
    assert "ACME SRL" not in stored_text

    # GET the template: variables visible like any normal template
    get_response = await async_client.get(
        f"/api/v1/templates/{template_id}", headers=auth_headers
    )
    assert get_response.status_code == 200
    assert set(get_response.json()["variables"]) == {"client_name", "company"}


# ── from-example: 422 validation errors ───────────────────────────────────────


@pytest.mark.asyncio
async def test_from_example_empty_mappings_returns_422(async_client, auth_headers):
    response = await async_client.post(
        "/api/v1/templates/from-example",
        headers=auth_headers,
        data={"name": "Sin mapeos", "mappings": "[]"},
        files=_docx_file(),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_from_example_invalid_json_mappings_returns_422(
    async_client, auth_headers
):
    response = await async_client.post(
        "/api/v1/templates/from-example",
        headers=auth_headers,
        data={"name": "JSON roto", "mappings": "not-a-json"},
        files=_docx_file(),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_from_example_bad_variable_name_returns_422(async_client, auth_headers):
    response = await async_client.post(
        "/api/v1/templates/from-example",
        headers=auth_headers,
        data={
            "name": "Variable mala",
            "mappings": json.dumps(
                [{"text": "JUAN PEREZ", "variable": "ClientName"}]
            ),
        },
        files=_docx_file(),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_from_example_duplicate_texts_returns_422(async_client, auth_headers):
    response = await async_client.post(
        "/api/v1/templates/from-example",
        headers=auth_headers,
        data={
            "name": "Textos duplicados",
            "mappings": json.dumps(
                [
                    {"text": "JUAN PEREZ", "variable": "uno"},
                    {"text": "JUAN PEREZ", "variable": "dos"},
                ]
            ),
        },
        files=_docx_file(),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_from_example_missing_text_returns_422_with_missing_list(
    async_client, auth_headers
):
    response = await async_client.post(
        "/api/v1/templates/from-example",
        headers=auth_headers,
        data={
            "name": "Texto inexistente",
            "mappings": json.dumps(
                [
                    {"text": "NO ESTA EN EL DOCUMENTO", "variable": "uno"},
                    {"text": "JUAN PEREZ", "variable": "client_name"},
                ]
            ),
        },
        files=_docx_file(),
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["missing_texts"] == ["NO ESTA EN EL DOCUMENTO"]
    assert "NO ESTA EN EL DOCUMENTO" in detail["message"]


@pytest.mark.asyncio
async def test_from_example_empty_file_returns_400(async_client, auth_headers):
    response = await async_client.post(
        "/api/v1/templates/from-example",
        headers=auth_headers,
        data={
            "name": "Archivo vacío",
            "mappings": json.dumps([{"text": "X", "variable": "x"}]),
        },
        files=_docx_file(content=b""),
    )
    assert response.status_code == 400
