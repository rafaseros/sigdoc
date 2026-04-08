# Delta for template-management

## MODIFIED Requirements

### Requirement: List Templates

`GET /templates` MUST return only templates the requesting user can access: templates they own OR have been explicitly shared. Admins MUST receive all templates within their tenant.
(Previously: non-admin users saw only templates they created; admins saw all tenant templates)

#### Scenario: Regular user sees owned + shared

- GIVEN user A owns T1 and has shared access to T2
- WHEN user A calls `GET /templates`
- THEN T1 and T2 MUST both appear; T1 with `access_type: "owned"`, T2 with `access_type: "shared"`

#### Scenario: Admin sees all tenant templates

- GIVEN tenant admin in a tenant with 5 templates owned by various users
- WHEN admin calls `GET /templates`
- THEN all 5 templates MUST appear

#### Scenario: User with no templates or shares sees empty list

- GIVEN user A owns nothing and has no shares
- WHEN user A calls `GET /templates`
- THEN the response MUST return an empty list with `total: 0`

---

### Requirement: Upload New Version

Only the template owner MUST be allowed to upload a new version. Users with shared access and users who have no relation to the template MUST be rejected with 403.
(Previously: any authenticated tenant user could upload a new version to any template they could access)

#### Scenario: Owner uploads new version successfully

- GIVEN user A owns template T (current_version = 1)
- WHEN user A calls `POST /templates/{T.id}/versions` with a valid .docx
- THEN the response MUST be 201
- AND `T.current_version` MUST be 2

#### Scenario: Shared user cannot upload new version

- GIVEN user B has shared access to template T
- WHEN user B calls `POST /templates/{T.id}/versions`
- THEN the response MUST be 403 with message indicating only the owner may version

#### Scenario: Unrelated user cannot upload new version

- GIVEN user C has no relation to template T
- WHEN user C calls `POST /templates/{T.id}/versions`
- THEN the response MUST be 403

---

### Requirement: Delete Template

Only the template owner or a tenant admin MUST be allowed to delete a template.
(Previously: any authenticated tenant user could delete any template they could access)

#### Scenario: Owner deletes successfully

- GIVEN user A owns template T
- WHEN user A calls `DELETE /templates/{T.id}`
- THEN the response MUST be 204
- AND all associated `template_shares` records MUST be cascade-deleted

#### Scenario: Admin can delete any template

- GIVEN tenant admin and template T owned by user A
- WHEN admin calls `DELETE /templates/{T.id}`
- THEN the response MUST be 204

#### Scenario: Shared user cannot delete

- GIVEN user B has shared access to template T
- WHEN user B calls `DELETE /templates/{T.id}`
- THEN the response MUST be 403

#### Scenario: Unrelated user cannot delete

- GIVEN user C has no relation to template T
- WHEN user C calls `DELETE /templates/{T.id}`
- THEN the response MUST be 403

---

### Requirement: Get Template Detail

`GET /templates/{id}` MUST return a template only if the requesting user is the owner, has shared access, or is a tenant admin. Others MUST receive 403.
(Previously: any authenticated tenant user could get any template detail)

#### Scenario: Owner gets own template

- GIVEN user A owns template T
- WHEN user A calls `GET /templates/{T.id}`
- THEN the response MUST be 200 with full template detail

#### Scenario: Shared user gets template detail

- GIVEN user B has shared access to template T
- WHEN user B calls `GET /templates/{T.id}`
- THEN the response MUST be 200

#### Scenario: Unrelated user is denied

- GIVEN user C has no relation to template T
- WHEN user C calls `GET /templates/{T.id}`
- THEN the response MUST be 403
