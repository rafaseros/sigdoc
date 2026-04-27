"""Smoke tests — unrouted endpoints must return 404 after single-org-cutover Phase 1.

Covers:
- POST /auth/signup          → 404 (handler removed, T-1-01)
- GET  /auth/verify-email    → 404 (handler removed, T-1-01)
- POST /auth/resend-verification → 404 (handler removed, T-1-01)
- POST /auth/forgot-password → 404 (handler removed, T-1-02)
- POST /auth/reset-password  → 404 (handler removed, T-1-02)
- GET  /tiers                → 404 (router include removed, T-1-03)
- GET  /usage                → 404 (router include removed, T-1-03)

Design: D-01, D-12  REQs: REQ-SOS-01, REQ-SOS-02, REQ-SOS-03
"""

from __future__ import annotations

import pytest

BASE = "/api/v1"


# ── parametrized 404 table ────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "method,path",
    [
        ("POST", f"{BASE}/auth/signup"),
        ("GET",  f"{BASE}/auth/verify-email"),
        ("POST", f"{BASE}/auth/resend-verification"),
        ("POST", f"{BASE}/auth/forgot-password"),
        ("POST", f"{BASE}/auth/reset-password"),
        ("GET",  f"{BASE}/tiers"),
        ("GET",  f"{BASE}/usage"),
    ],
)
@pytest.mark.asyncio
async def test_unrouted_returns_404(async_client, method, path):
    """All removed/unregistered routes must respond with 404 Not Found."""
    response = await async_client.request(method, path)
    assert response.status_code == 404, (
        f"{method} {path} expected 404 but got {response.status_code}: {response.text}"
    )
