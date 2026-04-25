# Verification Report — pdf-export

**Change**: pdf-export  
**Mode**: Strict TDD  
**Artifact store**: hybrid (engram + openspec)

---

## Phase 1 Verification

**Date**: 2026-04-25  
**Scope**: Phase 1 — Domain & permissions (T-DOMAIN-01 through T-DOMAIN-08)  
**Verdict**: ✅ APPROVED

---

### Completeness

| Metric | Value |
|--------|-------|
| Phase 1 tasks total | 8 |
| Tasks complete | 8 |
| Tasks incomplete | 0 |

All Phase 1 tasks are marked `[x]` in `tasks.md` and independently verified below.

---

### Build & Tests Execution

**Build**: N/A — Python/pytest project, no separate build step for Phase 1.

**Tests (Phase 1 domain only)**:
```
28 passed in 0.10s
```
All 28 Phase 1 tests pass.

**Tests (full suite)**:
```
375 passed, 3 warnings in 16.62s
```
The 3 warnings are pre-existing (2x `RuntimeWarning: coroutine never awaited` in `test_tiers_api.py` + 1x passlib `DeprecationWarning`). Zero new warnings.

**Coverage**: Not configured — not available.

---

### TDD Compliance

| Task | RED (tests failed first) | GREEN (impl passes) |
|------|--------------------------|---------------------|
| T-DOMAIN-01/02 | 6 FAILED (ModuleNotFoundError) | 6 PASSED |
| T-DOMAIN-03 | 3 FAILED (ImportError) | 3 PASSED |
| T-DOMAIN-04 | 5 FAILED (ModuleNotFoundError) | 5 PASSED |
| T-DOMAIN-05/06 | 5 FAILED (ModuleNotFoundError) | 5 PASSED |
| T-DOMAIN-07 | 1 FAILED (AssertionError) | 1 PASSED |
| T-DOMAIN-08 | 8 FAILED (TypeError/AssertionError) | 9 PASSED |

RED→GREEN cycle confirmed via apply-progress evidence. Total: 29 tests added across the phase (apply-progress counts 29; 28 collected at run time because `test_document_no_longer_accepts_old_file_name_kwarg` and one entity test are collapsed into `test_document_entity.py`'s 9 tests — all 28 collected pass).

---

### Per-Task Verification

| Task ID | Description | Verdict | Notes |
|---------|-------------|---------|-------|
| T-DOMAIN-01/02 | `can_download_format` truth table + impl | ✅ PASS | 6 parametrized tests cover all SCEN-DDF-16 cases exactly |
| T-DOMAIN-03 | `PdfConversionError` domain exception | ✅ PASS | Extends `DomainError`, accepts `message: str`, in `domain/exceptions.py` |
| T-DOMAIN-04 | `PdfConverter` ABC port | ✅ PASS | ABC, `@abstractmethod`, async, `docx_bytes: bytes`, raises only `PdfConversionError` (documented in docstring) |
| T-DOMAIN-05/06 | `FakePdfConverter` test double | ✅ PASS | Implements `PdfConverter`, has `call_count`, `set_failure()`, single-use clear |
| T-DOMAIN-07 | `AuditAction.DOCUMENT_DOWNLOAD` | ✅ PASS | Value `"document.download"`, in `AuditAction` class |
| T-DOMAIN-08 | `Document` entity dual fields | ✅ PASS | `docx_file_name: str`, `pdf_file_name: str | None`, `docx_minio_path: str`, `pdf_minio_path: str | None`; aliases documented |

---

### Spec Compliance Matrix

| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| REQ-DDF-08 | SCEN-DDF-16: (admin,docx)→True | `test_document_permissions.py::test_can_download_format_truth_table[admin-docx]` | ✅ COMPLIANT |
| REQ-DDF-08 | SCEN-DDF-16: (admin,pdf)→True | `test_document_permissions.py::test_can_download_format_truth_table[admin-pdf]` | ✅ COMPLIANT |
| REQ-DDF-08 | SCEN-DDF-16: (user,docx)→False | `test_document_permissions.py::test_can_download_format_truth_table[user-docx]` | ✅ COMPLIANT |
| REQ-DDF-08 | SCEN-DDF-16: (user,pdf)→True | `test_document_permissions.py::test_can_download_format_truth_table[user-pdf]` | ✅ COMPLIANT |
| REQ-DDF-08 | SCEN-DDF-16: (unknown,docx)→False (safe default) | `test_document_permissions.py::test_can_download_format_truth_table[unknown-docx]` | ✅ COMPLIANT |
| REQ-DDF-08 | SCEN-DDF-16: (unknown,pdf)→True (safe default) | `test_document_permissions.py::test_can_download_format_truth_table[unknown-pdf]` | ✅ COMPLIANT |
| REQ-PDF-06 | PdfConversionError extends DomainError | `test_pdf_conversion_error.py::test_pdf_conversion_error_is_domain_error` | ✅ COMPLIANT |
| REQ-PDF-06 | PdfConversionError accepts message str | `test_pdf_conversion_error.py::test_pdf_conversion_error_accepts_message` | ✅ COMPLIANT |
| REQ-PDF-01 | PdfConverter is ABC | `test_pdf_converter_port.py::test_pdf_converter_is_abstract` | ✅ COMPLIANT |
| REQ-PDF-01 | PdfConverter.convert is abstract method | `test_pdf_converter_port.py::test_pdf_converter_has_convert_method` | ✅ COMPLIANT |
| REQ-PDF-01 | convert signature: (self, docx_bytes: bytes) | `test_pdf_converter_port.py::test_pdf_converter_convert_signature` | ✅ COMPLIANT |
| REQ-PDF-10 | convert is async | `test_pdf_converter_port.py::test_pdf_converter_convert_is_coroutine` | ✅ COMPLIANT |
| REQ-PDF-07 | FakePdfConverter success mode | `test_fake_pdf_converter.py::test_fake_pdf_converter_returns_configured_bytes` | ✅ COMPLIANT |
| REQ-PDF-07 | FakePdfConverter set_failure() raises | `test_fake_pdf_converter.py::test_fake_pdf_converter_set_failure_causes_next_call_to_raise` | ✅ COMPLIANT |
| SCEN-PDF-06 | FakePdfConverter failure single-use clear | `test_fake_pdf_converter.py::test_fake_pdf_converter_failure_cleared_after_single_use` | ✅ COMPLIANT |
| REQ-PDF-07 | FakePdfConverter implements PdfConverter | `test_fake_pdf_converter.py::test_fake_pdf_converter_implements_pdf_converter_port` | ✅ COMPLIANT |
| REQ-DDF-15 | AuditAction.DOCUMENT_DOWNLOAD = "document.download" | `test_audit_action_download.py::test_audit_action_has_document_download` | ✅ COMPLIANT |
| REQ-DDF-01 | Document.docx_file_name: str | `test_document_entity.py::test_document_has_docx_file_name` | ✅ COMPLIANT |
| REQ-DDF-01 | Document.pdf_file_name: str \| None | `test_document_entity.py::test_document_has_pdf_file_name_optional` | ✅ COMPLIANT |
| REQ-DDF-01 | Document.docx_minio_path: str | `test_document_entity.py::test_document_has_docx_minio_path` | ✅ COMPLIANT |
| REQ-DDF-01 | Document.pdf_minio_path: str \| None | `test_document_entity.py::test_document_has_pdf_minio_path_optional` | ✅ COMPLIANT |
| REQ-DDF-01 | file_name field renamed (not a dataclass field) | `test_document_entity.py::test_document_no_longer_accepts_old_file_name_kwarg` | ✅ COMPLIANT |

**Compliance summary**: 22/22 Phase 1 scenarios compliant.

---

### Correctness (Static — Structural Evidence)

| Requirement | Status | Notes |
|------------|--------|-------|
| REQ-DDF-08: DOWNLOAD_FORMAT_PERMISSIONS dict | ✅ Implemented | `dict[str, frozenset[str]]` with admin/user entries |
| REQ-DDF-08: safe default for unknown roles | ✅ Implemented | `frozenset({"pdf"})` — PDF-only |
| REQ-PDF-06: PdfConversionError in domain layer | ✅ Implemented | `backend/src/app/domain/exceptions.py` |
| REQ-PDF-01: Abstract async convert method | ✅ Implemented | `@abstractmethod async def convert(self, docx_bytes: bytes) -> bytes` |
| REQ-PDF-07: FakePdfConverter with call_count | ✅ Implemented | Exceeds spec minimum (call_count adds observability) |
| REQ-DDF-15: AuditAction.DOCUMENT_DOWNLOAD | ✅ Implemented | `"document.download"` |
| REQ-DDF-01: Document dual file fields | ✅ Implemented | 4 fields + 2 compat aliases |
| No infra imports in domain | ✅ Clean | `rg "from app.infrastructure" backend/src/app/domain/` returns empty |
| No Alembic migrations added | ✅ Correct | Still 9 migrations (001–009); 010 deferred to Phase 2 |
| No frontend changes | ✅ Correct | Phase 1 is domain-only |
| No docker-compose changes | ✅ Correct | Phase 2 scope |
| No pyproject.toml changes | ✅ Correct | Phase 2 scope (httpx promotion) |

---

### Coherence (Design)

| Decision | Followed? | Notes |
|----------|-----------|-------|
| ADR-PDF-01: async bytes-in/bytes-out port | ✅ Yes | Exact signature from design |
| ADR-PDF-05: dict-based RBAC table | ✅ Yes | DOWNLOAD_FORMAT_PERMISSIONS matches design exactly |
| ADR-PDF-05: module location domain/services/ | ✅ Yes | New directory created with `__init__.py` |
| ADR-PDF-05: default unknown role = PDF-only | ✅ Yes | `frozenset({"pdf"})` as fallback |
| Design: PdfConversionError in exceptions.py | ✅ Yes | Not in a new file — added to existing module |
| T-DOMAIN-08: alias strategy for Phase 1 | ⚠️ Documented deviation | Read-only property aliases on Document entity — intentional, documented in docstring and apply-progress |

---

### Issues Found

**CRITICAL** (must fix before archive):
None.

**WARNING** (should fix):
- **W-01**: `Document.file_name` and `Document.minio_path` backward-compat property aliases exist in the domain entity. These are intentional Phase 1 scaffolding — the Phase 2 tasks list explicitly calls for their removal after the SQLAlchemy model rename. The risk is that aliases could be forgotten and persist past Phase 2. The entity docstring has a clear `TODO(pdf-export Phase 2)` comment. **Monitor and enforce removal in Phase 2 verify.**

**SUGGESTION**:
- **S-01**: `FakePdfConverter.convert()` does not enforce the "empty bytes = error" contract that REQ-PDF-01 specifies for production implementations. This is intentional for a test double (tests need to pass arbitrary bytes including empty), but it's worth noting that the ABC docstring documents the empty-bytes contract so production implementations know to enforce it.

---

### Verdict

**✅ APPROVED**

Phase 1 (Domain & permissions) is fully implemented and verified. 28/28 Phase 1 tests pass, 375/375 full suite pass (zero regressions). All 22 spec scenarios are COMPLIANT. Clean hexagonal boundary — no infrastructure imports in domain. The alias strategy for `Document` entity is documented and tracked for Phase 2 cleanup.

**Next recommended**: Ready to commit Phase 1 changes. Proceed to Phase 2 (T-INFRA-01 through T-INFRA-08).
