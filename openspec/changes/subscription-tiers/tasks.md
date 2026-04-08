# Tasks: subscription-tiers

## Phase 1: Migration + Domain Foundation

- [x] 1.1 Create `migrations/005_subscription_tiers.py` — CREATE subscription_tiers table, INSERT Free/Pro/Enterprise seed rows (uuid5 deterministic UUIDs), ALTER tenants ADD tier_id UUID FK NOT NULL DEFAULT free_uuid, backfill existing tenants
- [x] 1.2 Create `domain/entities/subscription_tier.py` — frozen dataclass SubscriptionTier with all fields (None = unlimited); export FREE_TIER_ID, PRO_TIER_ID, ENTERPRISE_TIER_ID constants
- [x] 1.3 Create `domain/ports/subscription_tier_repository.py` — abstract port: get_by_id(UUID), get_by_slug(str), list_active() -> list[SubscriptionTier]
- [x] 1.4 Modify `domain/entities/tenant.py` — add `tier_id: UUID | None = None`
- [x] 1.5 Modify `domain/exceptions.py` — add QuotaExceededError(limit_type, limit_value, current_usage, tier_name); keep BulkLimitExceededError untouched
- [x] 1.6 Modify `domain/ports/user_repository.py` — add abstract `count_active_by_tenant(tenant_id: UUID) -> int`
- [x] 1.7 Modify `domain/ports/template_repository.py` — add abstract `count_by_tenant(tenant_id: UUID) -> int` and `count_shares(template_id: UUID) -> int`

**TDD**: Write unit test file `tests/domain/test_subscription_tier_entity.py` — test None limits, tier constants, dataclass immutability.

## Phase 2: Infrastructure (ORM + Repos)

- [x] 2.1 Create `infrastructure/persistence/models/subscription_tier.py` — SubscriptionTierModel (no TenantMixin; global table), all columns mapped
- [x] 2.2 Modify `infrastructure/persistence/models/tenant.py` — add tier_id column + ForeignKey + relationship to SubscriptionTierModel
- [x] 2.3 Create `infrastructure/persistence/repositories/subscription_tier_repository.py` — SQLAlchemySubscriptionTierRepository implementing get_by_id, get_by_slug, list_active (is_active=True, ordered by monthly_document_limit ASC NULLS LAST)
- [x] 2.4 Modify `infrastructure/persistence/repositories/user_repository.py` — implement count_active_by_tenant (SELECT COUNT(*) WHERE tenant_id = X AND is_active = True)
- [x] 2.5 Modify `infrastructure/persistence/repositories/template_repository.py` — implement count_by_tenant and count_shares(template_id)

**TDD**: Create `tests/infrastructure/test_subscription_tier_repository.py` — test list_active ordering, get_by_slug hit/miss, count methods return correct integers.

## Phase 3: QuotaService + Fakes

- [x] 3.1 Create `application/services/quota_service.py` — QuotaService with constructor deps (tier_repo, usage_repo, template_repo, user_repo); implement _load_tier, get_tier_for_tenant, check_document_quota, check_template_limit, check_user_limit, check_bulk_limit (resolution order: user override → tier → 10), check_share_limit, get_usage_summary
- [x] 3.2 Create `tests/fakes/fake_subscription_tier_repository.py` — in-memory FakeSubscriptionTierRepository seeded with Free/Pro/Enterprise tiers
- [x] 3.3 Create `tests/fakes/fake_quota_service.py` — FakeQuotaService with `exceeded_resource: str | None`; raises QuotaExceededError for the configured resource check

**TDD RED→GREEN**: Write `tests/application/test_quota_service.py` FIRST — cover: None limit skips check, limit exceeded raises with correct fields, bulk override wins over tier, unlimited (None) never raises, check_share_limit counts tenant-wide.

## Phase 4: DI + Service Integration

- [x] 4.1 Modify `application/services/__init__.py` — add `get_quota_service()` factory; update `get_document_service()` and `get_template_service()` to inject QuotaService
- [x] 4.2 Modify `application/services/document_service.py` — add `quota_service: QuotaService | None = None` to constructor; call check_document_quota at top of generate_single(); call check_document_quota(additional=len(rows)) + check_bulk_limit at top of generate_bulk(); add optional tenant_id/user_bulk_override params to parse_excel_data()
- [x] 4.3 Modify `application/services/template_service.py` — add `quota_service: QuotaService | None = None` to constructor; call check_template_limit before upload_template(); call check_share_limit before share_template()
- [x] 4.4 Modify `presentation/api/v1/users.py` — inject `quota_service = Depends(get_quota_service)` in create_user(); call check_user_limit before user creation

**TDD**: Extend `tests/application/test_document_service.py` and `test_template_service.py` using FakeQuotaService — assert 429-equivalent raised on exceeded, pass when quota_service=None (existing 188 tests still pass).

## Phase 5: API + Schemas + Error Handler

- [x] 5.1 Create `presentation/schemas/tier.py` — Pydantic v2 schemas: TierPublicSchema, TiersListResponse, ResourceUsage (limit, current, percentage_used, near_limit), UsageSummary, TenantTierResponse; ConfigDict(from_attributes=True)
- [x] 5.2 Create `presentation/api/v1/tiers.py` — GET /api/v1/tiers (no auth, list_active()); GET /api/v1/tenant/tier (auth required, get_usage_summary from QuotaService, max 4 DB queries)
- [x] 5.3 Modify `main.py` — register tiers router; add global QuotaExceededError exception handler → HTTP 429 JSON {error, limit_type, limit_value, current_usage, tier_name}
- [x] 5.4 Modify `presentation/api/v1/usage.py` — enrich existing GET /api/v1/usage response with limit and percentage_used fields (optional when QuotaService not wired)

**TDD**: Create `tests/api/test_tiers_api.py` — test GET /tiers returns only active tiers ordered correctly, GET /tenant/tier returns correct usage/limit/percentage, unauthenticated 401, QuotaExceeded returns 429 with structured body.

## Phase 6: Frontend

- [x] 6.1 Create `frontend/src/features/subscription/api/keys.ts` — query key factory for tier endpoints
- [x] 6.2 Create `frontend/src/features/subscription/api/queries.ts` — useTenantTier() React Query hook (GET /api/v1/tenant/tier)
- [x] 6.3 Create `frontend/src/features/subscription/components/TierCard.tsx` — dashboard widget: plan name, progress bars (docs/templates/users/shares), green/yellow/red by percentage, upgrade CTA for Free plan
- [x] 6.4 Create `frontend/src/features/subscription/components/QuotaExceededDialog.tsx` — modal showing resource/limit/current; CTA "contact admin"; triggered by 429 interceptor
- [x] 6.5 Modify `frontend/src/shared/lib/api-client.ts` — add 429 response interceptor that fires QuotaExceededDialog
- [x] 6.6 Modify `frontend/src/routes/_authenticated.tsx` — mount QuotaExceededDialog + add Suscripción nav link; create /subscription route
- [x] 6.7 Modify `frontend/src/features/usage/components/UsageWidget.tsx` — add limit + progress bar alongside current count
- [x] 6.8 Modify `frontend/src/routes/_authenticated/users/index.tsx` — add "X/Y users" badge (admin only via tier context)
- [x] 6.9 Modify `frontend/src/routes/_authenticated/templates/index.tsx` — add "X/Y templates" badge

## Phase 7: Verification

- [x] 7.1 Run full test suite — all 188 pre-existing tests MUST pass; quota tests added in Phases 1-5 MUST pass
  - Result: 231 tests pass (43 new tests added), 0 failures
  - Tests created: test_quota_service.py (24), test_document_service.py +3, test_template_service.py +12, test_tiers_api.py (10)
  - Fixed: integration conftest MagicMock session, get_quota_service override
- [ ] 7.2 Run migration against local DB — verify subscription_tiers table exists, 3 seed rows present, all tenants have tier_id set to Free UUID
- [ ] 7.3 Manual smoke test GET /api/v1/tiers — returns 3 active tiers ordered Free→Pro→Enterprise
- [ ] 7.4 Manual smoke test GET /api/v1/tenant/tier — returns usage summary with percentage_used and near_limit flags
- [ ] 7.5 Manual smoke test quota enforcement — set tenant to Free, generate 51 docs, assert 429 with correct body
- [ ] 7.6 Manual smoke test frontend — TierCard renders, QuotaExceededDialog appears on 429, progress bars reflect usage
