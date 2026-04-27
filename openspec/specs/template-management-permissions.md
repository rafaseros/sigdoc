# Capability: template-management-permissions

## Purpose

Defines who may create and version templates. Introduces the `can_manage_own_templates` domain helper (True for `admin` and `template_creator`, False for all others), the `require_template_manager` FastAPI dependency that gates upload and new-version endpoints, and the frontend conditional rendering that hides the upload UI from `document_generator` users. Document generation remains ungated — visibility is enforced by existing template-repository share logic, not by a new capability.

## Requirements

### REQ-TMP-01: can_manage_own_templates helper

`can_manage_own_templates(role: str) -> bool` MUST reside in `backend/src/app/domain/services/permissions.py`. It MUST return `True` for `"admin"` and `"template_creator"`, and `False` for `"document_generator"` and any unknown role (safe-default deny).

### REQ-TMP-02: require_template_manager dependency

`require_template_manager` MUST be defined in `backend/src/app/presentation/api/dependencies.py` as a pre-bound dependency using `require_capability(can_manage_own_templates)`, following the same pattern as `require_user_manager` and `require_audit_viewer`.

### REQ-TMP-03: Upload endpoint gated by require_template_manager

`POST /templates/upload` MUST require `Depends(require_template_manager)`. Requests from authenticated users whose role returns `False` from `can_manage_own_templates` MUST receive HTTP 403.

### REQ-TMP-04: New-version endpoint gated by require_template_manager

`POST /templates/{template_id}/versions` MUST require `Depends(require_template_manager)`. Requests from authenticated users whose role returns `False` from `can_manage_own_templates` MUST receive HTTP 403.

### REQ-TMP-05: Document generation ungated by role

`document_generator` users MUST be permitted to call `POST /documents/generate` and `POST /documents/generate-bulk`. No new role gate is added to these endpoints. Template visibility (owned or explicitly shared) is enforced by the existing `template_repository` access logic; absence of a share record results in HTTP 403 from the service layer.

### REQ-TMP-06: Frontend canUploadTemplates helper

`canUploadTemplates(role: string): boolean` MUST reside in `frontend/src/shared/lib/permissions.ts`. It MUST mirror backend logic: return `true` for `"admin"` and `"template_creator"`, `false` for all other values.

### REQ-TMP-07: UploadTemplateDialog conditional render

The `<UploadTemplateDialog />` component MUST be rendered only when `canUploadTemplates(currentUser.role)` returns `true`. For a `document_generator` user, the upload dialog element MUST NOT be present in the DOM.

### REQ-TMP-08: Role labels export

`frontend/src/shared/lib/role-labels.ts` MUST export `ROLE_LABELS` typed as `Record<Role, string>` with the following Spanish mappings:
- `admin` → `"Administrador"`
- `template_creator` → `"Creador de plantillas"`
- `document_generator` → `"Generador de documentos"`

### REQ-TMP-09: Authenticated header role badge

The authenticated layout header MUST display the current user's role as a localized badge using `ROLE_LABELS`. Every authenticated user MUST see their role label on every page.

### REQ-TMP-10: EditUserDialog role Select options

The role `<Select>` inside `EditUserDialog` MUST present exactly three options using the Spanish labels from `ROLE_LABELS`. Submitting a role value outside the three valid options MUST be prevented client-side before the network call is made.

## Scenarios

### SCEN-TMP-01: can_manage_own_templates truth table (satisfies REQ-TMP-01)
**Given**: The `can_manage_own_templates` helper
**When**: Called with `"admin"`, `"template_creator"`, `"document_generator"`, and `"unknown"`
**Then**: Returns `True`, `True`, `False`, `False` respectively

### SCEN-TMP-02: document_generator blocked from upload (satisfies REQ-TMP-03)
**Given**: An authenticated user with `role="document_generator"`
**When**: User calls `POST /templates/upload` with a valid `.docx` file
**Then**: HTTP 403 is returned
**And**: No template is created

### SCEN-TMP-03: template_creator can upload (satisfies REQ-TMP-03)
**Given**: An authenticated user with `role="template_creator"`
**When**: User calls `POST /templates/upload` with a valid `.docx` file
**Then**: HTTP 201 is returned
**And**: The template is created and owned by that user

### SCEN-TMP-04: admin can upload (satisfies REQ-TMP-03)
**Given**: An authenticated user with `role="admin"`
**When**: User calls `POST /templates/upload` with a valid `.docx` file
**Then**: HTTP 201 is returned

### SCEN-TMP-05: document_generator blocked from versioning (satisfies REQ-TMP-04)
**Given**: An authenticated user with `role="document_generator"`
**And**: A template that has been shared with that user
**When**: User calls `POST /templates/{template_id}/versions` with a valid `.docx` file
**Then**: HTTP 403 is returned
**And**: No new version is created

### SCEN-TMP-06: template_creator can version own template (satisfies REQ-TMP-04)
**Given**: An authenticated user with `role="template_creator"` who owns a template
**When**: User calls `POST /templates/{template_id}/versions` with a valid `.docx` file
**Then**: HTTP 201 is returned
**And**: A new version record is created

### SCEN-TMP-07: document_generator generates from shared template (satisfies REQ-TMP-05)
**Given**: An authenticated user with `role="document_generator"`
**And**: A template explicitly shared with that user
**When**: User calls `POST /documents/generate` with a `template_version_id` belonging to that template
**Then**: HTTP 201 is returned
**And**: The document is generated successfully

### SCEN-TMP-08: document_generator blocked from non-shared template (satisfies REQ-TMP-05)
**Given**: An authenticated user with `role="document_generator"`
**And**: A template that is NOT shared with that user (no share record exists)
**When**: User calls `POST /documents/generate` with a `template_version_id` belonging to that template
**Then**: HTTP 403 is returned (`TemplateAccessDeniedError` raised by `_check_access` in `template_service.py`, mapped to 403 in the documents endpoint)
**And**: No document is created

### SCEN-TMP-09: Upload button absent for document_generator (satisfies REQ-TMP-07)
**Given**: The templates page rendered for a `document_generator` user
**When**: The page is fully mounted
**Then**: The `<UploadTemplateDialog />` component is NOT present in the DOM

### SCEN-TMP-10: Upload button present for template_creator (satisfies REQ-TMP-07)
**Given**: The templates page rendered for a `template_creator` user
**When**: The page is fully mounted
**Then**: The upload template button IS present in the DOM
**And**: Clicking it opens the upload dialog
