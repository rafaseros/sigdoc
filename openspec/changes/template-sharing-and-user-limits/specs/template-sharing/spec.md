# template-sharing Specification

## Purpose

Defines visibility rules, share/unshare mechanics, and the permission model for templates. Templates are private by default; the owner controls who else may access them.

## Requirements

### Requirement: Private by Default

A newly created template MUST be visible only to its owner (`created_by`) and tenant admins. No other tenant user SHALL see it unless an explicit share is granted.

#### Scenario: New template invisible to peer

- GIVEN user A and user B belong to the same tenant
- WHEN user A creates a template
- THEN user B's template listing MUST NOT include that template
- AND user B's direct `GET /templates/{id}` request MUST return 403

#### Scenario: Owner sees own template immediately

- GIVEN user A has just uploaded a template
- WHEN user A lists templates
- THEN the new template MUST appear in the result

#### Scenario: Admin sees all tenant templates

- GIVEN a tenant admin and user A in the same tenant
- WHEN user A creates a template
- THEN the admin's listing MUST include user A's template

---

### Requirement: Share with Specific User

The template owner MUST be able to grant access to any active user in the same tenant. Sharing creates a `template_shares` record.

#### Scenario: Owner shares successfully

- GIVEN user A owns template T and user B is active in the same tenant
- WHEN user A calls `POST /templates/{T.id}/shares` with `{ "user_id": B.id }`
- THEN the response MUST be 201
- AND user B's listing MUST now include template T with `access_type: "shared"`

#### Scenario: Non-owner cannot share

- GIVEN user B has shared access to template T (not owner)
- WHEN user B calls `POST /templates/{T.id}/shares`
- THEN the response MUST be 403
- AND the error message MUST state that only the owner may share

#### Scenario: Cannot share with user outside tenant

- GIVEN user A owns template T and user C belongs to a different tenant
- WHEN user A tries to share T with user C
- THEN the response MUST be 422

#### Scenario: Duplicate share is idempotent

- GIVEN user A has already shared template T with user B
- WHEN user A shares T with user B again
- THEN the response MUST be 200 (not 409)
- AND no duplicate `template_shares` row SHALL be created

---

### Requirement: Unshare

The template owner MUST be able to revoke a previously granted share.

#### Scenario: Owner unshares successfully

- GIVEN user A owns template T and user B has shared access
- WHEN user A calls `DELETE /templates/{T.id}/shares/{B.id}`
- THEN the response MUST be 204
- AND user B's listing MUST no longer include template T

#### Scenario: Non-owner cannot unshare

- GIVEN user B has shared access to template T
- WHEN user B calls `DELETE /templates/{T.id}/shares/{A.id}`
- THEN the response MUST be 403

---

### Requirement: List Returns Owned and Shared Templates

`GET /templates` MUST return all templates the requesting user owns OR has been explicitly shared, differentiated by an `access_type` field.

| `access_type` | Meaning |
|---------------|---------|
| `"owned"` | Requesting user is the creator |
| `"shared"` | Access was granted via share |

Admins MUST receive all tenant templates; `access_type` for admins SHALL be `"owned"` for their own and `"admin"` for others.

#### Scenario: Mixed listing for regular user

- GIVEN user A owns T1 and has shared access to T2 (owned by user B)
- WHEN user A lists templates
- THEN the response MUST include T1 with `access_type: "owned"` and T2 with `access_type: "shared"`

#### Scenario: Admin listing includes all

- GIVEN tenant admin and two users each with one private template
- WHEN admin lists templates
- THEN all templates MUST appear in the response

---

### Requirement: Shared Permission — Read and Generate Only

A user with shared access MUST be able to view template details and generate documents. They MUST NOT be able to upload new versions or delete the template.

#### Scenario: Shared user can generate

- GIVEN user B has shared access to template T
- WHEN user B calls `POST /documents/generate` referencing a version of T
- THEN the response MUST be 201

#### Scenario: Shared user cannot version

- GIVEN user B has shared access to template T
- WHEN user B calls `POST /templates/{T.id}/versions`
- THEN the response MUST be 403

#### Scenario: Shared user cannot delete

- GIVEN user B has shared access to template T
- WHEN user B calls `DELETE /templates/{T.id}`
- THEN the response MUST be 403
