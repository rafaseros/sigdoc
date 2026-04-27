"""Unit tests for FakeTemplateRepository.get_share_for_user (TDD RED → GREEN)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from tests.fakes import FakeTemplateRepository


TENANT_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
OWNER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
USER_B_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


@pytest.mark.asyncio
async def test_get_share_for_user_returns_share(fake_template_repo: FakeTemplateRepository):
    """get_share_for_user returns the TemplateShare when the row exists."""
    template_id = uuid.uuid4()

    share = await fake_template_repo.add_share(
        template_id=template_id,
        user_id=USER_B_ID,
        tenant_id=TENANT_ID,
        shared_by=OWNER_ID,
    )

    result = await fake_template_repo.get_share_for_user(template_id, USER_B_ID)

    assert result is not None
    assert result.template_id == template_id
    assert result.user_id == USER_B_ID
    assert result.shared_by == OWNER_ID
    assert result.id == share.id


@pytest.mark.asyncio
async def test_get_share_for_user_returns_none_when_no_match(
    fake_template_repo: FakeTemplateRepository,
):
    """get_share_for_user returns None when no share row exists for the user."""
    template_id = uuid.uuid4()
    unrelated_user_id = uuid.uuid4()

    # Add a share for a different user so the template exists in _shares
    await fake_template_repo.add_share(
        template_id=template_id,
        user_id=USER_B_ID,
        tenant_id=TENANT_ID,
        shared_by=OWNER_ID,
    )

    result = await fake_template_repo.get_share_for_user(template_id, unrelated_user_id)

    assert result is None


@pytest.mark.asyncio
async def test_get_share_for_user_returns_none_for_unknown_template(
    fake_template_repo: FakeTemplateRepository,
):
    """get_share_for_user returns None when the template has no shares at all."""
    result = await fake_template_repo.get_share_for_user(uuid.uuid4(), USER_B_ID)

    assert result is None
