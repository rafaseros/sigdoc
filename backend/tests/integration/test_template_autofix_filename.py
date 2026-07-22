"""Fix 3 — Content-Disposition filename sanitization on the auto-fix endpoint.

POST /api/v1/templates/auto-fix builds its download filename from the RAW
upload filename (`file.filename`). Unlike the version-download endpoints, it
did not sanitize it, so quotes / CRLF / control chars in a crafted filename
could break out of the quoted header value (header injection).

These tests exercise the shared header builder directly (deterministic, no
multipart round-trip for the adversarial chars) plus the endpoint end-to-end
to prove it now emits the safe ASCII fallback + RFC 5987 `filename*` form.
"""

from __future__ import annotations

import io

import pytest

from app.presentation.api.v1.templates import _content_disposition_attachment
from app.presentation.middleware.tenant import get_current_user


# ---------------------------------------------------------------------------
# Shared header builder — the reused sanitization helper
# ---------------------------------------------------------------------------


def test_helper_neutralizes_quote_and_crlf_and_encodes_utf8():
    """A crafted filename with a double-quote and CRLF cannot break out of
    the quoted fallback nor inject header content, and its exact bytes are
    percent-encoded in filename*."""
    header = _content_disposition_attachment('ma"lo\r\nintr.docx')

    # Exactly two double-quotes — the fallback delimiters, nothing embedded.
    assert header.count('"') == 2
    # No raw CR/LF survive (would enable header injection).
    assert "\r" not in header and "\n" not in header
    # filename* carries the exact bytes, percent-encoded.
    assert "filename*=UTF-8''" in header
    assert "%22" in header  # the double-quote, encoded
    assert "%0D" in header and "%0A" in header  # the CRLF, encoded


def test_helper_encodes_non_ascii_and_keeps_ascii_fallback():
    """Non-ASCII names get an ASCII-transliterated fallback plus the exact
    UTF-8 name in filename*."""
    header = _content_disposition_attachment("münchen.docx")

    assert 'filename="munchen.docx"' in header  # NFKD ASCII fallback
    assert "filename*=UTF-8''m%C3%BCnchen.docx" in header


def test_helper_empty_fallback_defaults():
    """When transliteration leaves nothing safe, a stable default is used for
    the fallback (filename* still carries the original)."""
    header = _content_disposition_attachment("™.docx")
    assert 'filename="' in header
    # Fallback never collapses to an empty quoted value.
    assert 'filename=""' not in header


# ---------------------------------------------------------------------------
# auto-fix endpoint — end-to-end safe header
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auto_fix_emits_sanitized_content_disposition(
    async_client, app, auth_headers, monkeypatch, fake_template_engine
):
    """The auto-fix download must carry the safe ASCII fallback + RFC 5987
    filename* form (like the version-download endpoints), never the raw
    upload filename interpolated straight into the quoted header."""
    # auto-fix calls get_template_engine() directly (outside DI); point it at
    # the fake so validation/auto_fix succeed on arbitrary bytes.
    monkeypatch.setattr(
        "app.presentation.api.v1.templates.get_template_engine",
        lambda: fake_template_engine,
    )

    # Default conftest user is authenticated; no override needed.
    response = await async_client.post(
        "/api/v1/templates/auto-fix",
        headers=auth_headers,
        files={
            "file": (
                "reporte_münchen.docx",
                io.BytesIO(b"fake-docx-bytes"),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert response.status_code == 200, response.text
    disposition = response.headers["content-disposition"]
    assert "attachment" in disposition
    # Safe RFC 5987 form present (absent in the vulnerable raw-filename build).
    assert "filename*=UTF-8''" in disposition
    # Exactly the two fallback delimiters — no breakout.
    assert disposition.count('"') == 2
