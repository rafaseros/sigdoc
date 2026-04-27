import type { Role } from "./permissions";

export const ROLE_LABELS: Record<Role, string> = {
  admin: "Administrador",
  template_creator: "Creador de plantillas",
  document_generator: "Generador de documentos",
};

export function getRoleLabel(role: string | undefined): string {
  if (!role) return "Usuario";
  return ROLE_LABELS[role as Role] ?? "Usuario";
}
