"""Unit tests for slug_utils.

Spec: REQ-SIGNUP-05 — slugify + unique_slug
"""

import pytest

from app.application.services.slug_utils import slugify, unique_slug


# ── slugify ───────────────────────────────────────────────────────────────────


def test_slugify_basic():
    assert slugify("Acme Corp") == "acme-corp"


def test_slugify_lowercase():
    assert slugify("HELLO WORLD") == "hello-world"


def test_slugify_strips_accents():
    assert slugify("Héllo Wörld") == "hello-world"


def test_slugify_collapses_multiple_spaces():
    assert slugify("foo  bar") == "foo-bar"


def test_slugify_collapses_multiple_hyphens():
    assert slugify("foo--bar") == "foo-bar"


def test_slugify_strips_leading_trailing_hyphens():
    assert slugify("-foo-") == "foo"


def test_slugify_special_chars_become_hyphens():
    assert slugify("Foo & Bar!") == "foo-bar"


def test_slugify_numbers_preserved():
    assert slugify("Company 123") == "company-123"


def test_slugify_empty_string_returns_org():
    assert slugify("") == "org"


def test_slugify_only_special_chars_returns_org():
    assert slugify("!@#$%") == "org"


def test_slugify_unicode_org_name():
    assert slugify("Ñoño Corp") == "nono-corp"


# ── unique_slug ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unique_slug_returns_base_when_free():
    async def not_taken(slug):
        return False

    result = await unique_slug("acme", not_taken)
    assert result == "acme"


@pytest.mark.asyncio
async def test_unique_slug_appends_2_when_base_taken():
    taken = {"acme"}

    async def exists(slug):
        return slug in taken

    result = await unique_slug("acme", exists)
    assert result == "acme-2"


@pytest.mark.asyncio
async def test_unique_slug_increments_until_free():
    taken = {"acme", "acme-2", "acme-3"}

    async def exists(slug):
        return slug in taken

    result = await unique_slug("acme", exists)
    assert result == "acme-4"


@pytest.mark.asyncio
async def test_unique_slug_no_collision():
    async def exists(slug):
        return False

    result = await unique_slug("my-org", exists)
    assert result == "my-org"
