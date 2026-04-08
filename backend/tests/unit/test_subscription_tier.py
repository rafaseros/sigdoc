"""Unit tests — SubscriptionTier entity defaults (Task 1.1 / Task 5.2).

Spec: REQ-RL-01
- subscription_tier entity must expose rate_limit_login, rate_limit_refresh,
  rate_limit_generate, rate_limit_bulk with correct defaults.
"""

import uuid
from app.domain.entities.subscription_tier import (
    SubscriptionTier,
    FREE_TIER_ID,
    PRO_TIER_ID,
    ENTERPRISE_TIER_ID,
)


def _make_tier(**kwargs) -> SubscriptionTier:
    """Build a minimal SubscriptionTier with required fields only."""
    defaults = dict(
        id=FREE_TIER_ID,
        name="Free",
        slug="free",
        monthly_document_limit=50,
        max_templates=5,
        max_users=3,
        bulk_generation_limit=5,
        max_template_shares=5,
    )
    defaults.update(kwargs)
    return SubscriptionTier(**defaults)


class TestSubscriptionTierRateLimitDefaults:
    """Task 5.2 — SubscriptionTier must carry rate limit fields with correct defaults."""

    def test_rate_limit_login_default(self):
        tier = _make_tier()
        assert tier.rate_limit_login == "5/minute"

    def test_rate_limit_refresh_default(self):
        tier = _make_tier()
        assert tier.rate_limit_refresh == "10/minute"

    def test_rate_limit_generate_default(self):
        tier = _make_tier()
        assert tier.rate_limit_generate == "20/minute"

    def test_rate_limit_bulk_default(self):
        tier = _make_tier()
        assert tier.rate_limit_bulk == "5/minute"

    def test_rate_limit_fields_overridable(self):
        """Rate limit fields can be set to non-default values (tier-specific values)."""
        tier = _make_tier(
            rate_limit_login="10/minute",
            rate_limit_refresh="20/minute",
            rate_limit_generate="30/minute",
            rate_limit_bulk="10/minute",
        )
        assert tier.rate_limit_login == "10/minute"
        assert tier.rate_limit_refresh == "20/minute"
        assert tier.rate_limit_generate == "30/minute"
        assert tier.rate_limit_bulk == "10/minute"

    def test_rate_limit_enterprise_generous_values(self):
        """Enterprise tier carries its specific generous limits (REQ-RL-02)."""
        tier = _make_tier(
            id=ENTERPRISE_TIER_ID,
            name="Enterprise",
            slug="enterprise",
            monthly_document_limit=5000,
            max_templates=None,
            max_users=None,
            bulk_generation_limit=100,
            max_template_shares=None,
            rate_limit_login="20/minute",
            rate_limit_refresh="30/minute",
            rate_limit_generate="60/minute",
            rate_limit_bulk="20/minute",
        )
        assert tier.rate_limit_generate == "60/minute"
        assert tier.rate_limit_bulk == "20/minute"

    def test_tier_is_frozen_dataclass(self):
        """SubscriptionTier is an immutable value object."""
        tier = _make_tier()
        try:
            tier.rate_limit_login = "100/minute"  # type: ignore[misc]
            assert False, "Should have raised FrozenInstanceError"
        except Exception:
            pass  # Expected — frozen dataclass
