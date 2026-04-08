# Spec: Admin Management Enhancements

**Change**: `admin-seed-and-email-workflows`
**Module**: `admin-management`
**Status**: specified

## Requirements

### REQ-ADMIN-01: Role Change via User Update

The `PUT /users/{user_id}` endpoint SHALL accept an optional `role` field in the request body.

**Valid roles**: `"admin"`, `"user"`

**Authorization**: Only users with `role="admin"` can change roles (existing `require_admin` guard applies).

### REQ-ADMIN-02: Last Admin Guard

When an admin attempts to demote another admin to `role="user"`:
- The system SHALL count the number of active admin users in the current tenant
- If only ONE active admin remains, the demotion SHALL be rejected with HTTP 409 and message: `"No se puede quitar el rol de administrador al ultimo admin del tenant"`
- If multiple admins exist, the demotion proceeds normally

**Edge cases**:
- Self-demotion follows the same rule (the last admin cannot demote themselves)
- Deactivating the last admin is also blocked (existing `deactivate_user` endpoint)

### REQ-ADMIN-03: Admin Can Edit All User Fields

Admins can update for any user in their tenant:
- `email` (with uniqueness check)
- `full_name`
- `role` (with last-admin guard)
- `is_active`
- `bulk_generation_limit`

### REQ-ADMIN-04: Frontend Role Selector

The `EditUserDialog` component SHALL include a role selector (dropdown or radio) with options `Admin` and `Usuario`.

The role selector SHALL be disabled when:
- The user being edited is the last remaining admin in the tenant

### REQ-ADMIN-05: Audit Logging for Role Changes

When a user's role is changed, the audit log entry SHALL include the old and new role values in the `details` field.

## Scenarios

### SCEN-ADMIN-01: Promote user to admin
**Given** an admin user and a regular user in the same tenant
**When** the admin sends `PUT /users/{userId}` with `{ "role": "admin" }`
**Then** the user's role is updated to `admin`
**And** an audit log entry is created with details `{ "role": "admin" }`

### SCEN-ADMIN-02: Demote admin to user (multiple admins)
**Given** two admin users in the same tenant
**When** admin A sends `PUT /users/{adminB}` with `{ "role": "user" }`
**Then** admin B's role is updated to `user`

### SCEN-ADMIN-03: Demote last admin (blocked)
**Given** only one admin user in the tenant
**When** the admin sends `PUT /users/{self}` with `{ "role": "user" }`
**Then** the request returns HTTP 409
**And** the role is NOT changed

### SCEN-ADMIN-04: Deactivate last admin (blocked)
**Given** only one admin user in the tenant
**When** the admin sends `DELETE /users/{self}`
**Then** the request returns HTTP 409
**And** the user is NOT deactivated

### SCEN-ADMIN-05: Invalid role value
**Given** an admin user
**When** the admin sends `PUT /users/{userId}` with `{ "role": "superadmin" }`
**Then** the request returns HTTP 422 (validation error)
