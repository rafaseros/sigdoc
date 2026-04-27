export type Role = "admin" | "template_creator" | "document_generator";

// NOTE: Authoritative source is backend/src/app/domain/services/permissions.py.
// Frontend mirrors for UX gating only — backend always re-validates.

export const canUploadTemplates = (role: Role | string | undefined): boolean =>
  role === "admin" || role === "template_creator";

export const canManageUsers = (role: Role | string | undefined): boolean =>
  role === "admin";

export const canViewAudit = (role: Role | string | undefined): boolean =>
  role === "admin";

export const canViewTenantUsage = (role: Role | string | undefined): boolean =>
  role === "admin";
