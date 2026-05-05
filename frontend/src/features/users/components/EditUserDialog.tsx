import { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  Check,
  ChevronRight,
  KeyRound,
  LoaderCircle,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/shared/lib/auth";
import type { Role } from "@/shared/lib/permissions";
import { ROLE_LABELS } from "@/shared/lib/role-labels";
import { useUpdateUser, useResetUserPassword, type UserResponse } from "../api";
import { RolePicker } from "./CreateUserDialog";

interface EditUserDialogProps {
  user: UserResponse;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function getInitials(email: string) {
  const local = email.split("@")[0] ?? email;
  const parts = local.split(/[._-]/).filter(Boolean);
  const first = parts[0]?.[0] ?? "?";
  const second = parts[1]?.[0] ?? parts[0]?.[1] ?? "";
  return (first + second).toUpperCase();
}

function rolePillClasses(role: string) {
  if (role === "admin") {
    return "bg-gradient-to-br from-[#004ac6] to-[#2563eb] text-white border-0 rounded-full";
  }
  if (role === "template_creator") {
    return "bg-[var(--bg-accent)] text-[var(--primary)] border-0 rounded-full hover:bg-[var(--bg-accent)]";
  }
  return "bg-[var(--bg-muted)] text-[var(--fg-2)] border-0 rounded-full hover:bg-[var(--bg-muted)]";
}

function roleLabel(role: string) {
  return ROLE_LABELS[role as Role] ?? role;
}

function statusLabel(active: boolean) {
  return active ? "Activo" : "Inactivo";
}

export function EditUserDialog({
  user,
  open,
  onOpenChange,
}: EditUserDialogProps) {
  const { user: currentUser } = useAuth();
  const [fullName, setFullName] = useState(user.full_name);
  const [isActive, setIsActive] = useState(user.is_active);
  const [role, setRole] = useState<Role>((user.role as Role) ?? "document_generator");

  const [showPasswordReset, setShowPasswordReset] = useState(false);
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const updateMutation = useUpdateUser();
  const resetPasswordMutation = useResetUserPassword();

  const isAdmin = currentUser?.role === "admin";
  const isEditingSelf = currentUser?.id === user.id;
  const canEditRole = isAdmin && !isEditingSelf;

  useEffect(() => {
    setFullName(user.full_name);
    setIsActive(user.is_active);
    setRole((user.role as Role) ?? "document_generator");
    setShowPasswordReset(false);
    setNewPassword("");
    setConfirmPassword("");
  }, [user]);

  // Compute live diff
  const diff: { key: string; from: string; to: string }[] = [];
  if (fullName.trim() && fullName !== user.full_name) {
    diff.push({ key: "Nombre", from: user.full_name, to: fullName });
  }
  if (canEditRole && role !== user.role) {
    diff.push({
      key: "Rol",
      from: roleLabel(user.role),
      to: roleLabel(role),
    });
  }
  if (isActive !== user.is_active) {
    diff.push({
      key: "Estado",
      from: statusLabel(user.is_active),
      to: statusLabel(isActive),
    });
  }
  const hasChanges = diff.length > 0;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    if (!fullName.trim()) {
      toast.error("El nombre completo es obligatorio");
      return;
    }

    if (!hasChanges) {
      toast.info("No hay cambios para guardar");
      return;
    }

    try {
      await updateMutation.mutateAsync({
        id: user.id,
        full_name: fullName.trim(),
        is_active: isActive,
        ...(canEditRole ? { role } : {}),
      });
      toast.success("Usuario actualizado con éxito");
      onOpenChange(false);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Error al actualizar usuario";
      toast.error(message);
    }
  }

  async function handleResetPassword() {
    if (newPassword.length < 8) {
      toast.error("La nueva contraseña debe tener al menos 8 caracteres");
      return;
    }

    if (newPassword !== confirmPassword) {
      toast.error("Las contraseñas no coinciden");
      return;
    }

    try {
      await resetPasswordMutation.mutateAsync({
        id: user.id,
        new_password: newPassword,
      });
      toast.success("Contraseña reseteada con éxito");
      setNewPassword("");
      setConfirmPassword("");
      setShowPasswordReset(false);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Error al resetear contraseña";
      toast.error(message);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[88vh] overflow-y-auto sm:max-w-2xl">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle className="text-xl font-bold tracking-tight">
              Editar usuario
            </DialogTitle>
            <DialogDescription>
              Modifique el nombre, el rol o el estado del usuario. El correo no
              puede cambiarse — sirve como identificador permanente.
            </DialogDescription>
          </DialogHeader>

          <div className="flex flex-col gap-4 py-4">
            {/* Identity card */}
            <div className="flex items-center gap-3 rounded-xl bg-white p-3.5 shadow-[var(--shadow-sm)] ring-1 ring-[rgba(195,198,215,0.30)]">
              <span className="inline-flex size-11 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-[#004ac6] to-[#2563eb] text-[13px] font-semibold text-white">
                {getInitials(user.email)}
              </span>
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-semibold text-[var(--fg-1)]">
                  {user.full_name}
                </div>
                <div className="truncate font-mono text-[11.5px] text-[var(--fg-3)]">
                  {user.email}
                </div>
              </div>
              <Badge className={rolePillClasses(user.role)}>
                {roleLabel(user.role)}
              </Badge>
            </div>

            {/* Editable fields */}
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="grid gap-1.5">
                <Label
                  htmlFor="edit-fullname"
                  className="text-xs font-semibold uppercase tracking-[0.04em] text-[var(--fg-3)]"
                >
                  Nombre completo
                </Label>
                <Input
                  id="edit-fullname"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Juan Pérez"
                  required
                />
              </div>

              <div className="grid gap-1.5">
                <Label
                  htmlFor="edit-email"
                  className="text-xs font-semibold uppercase tracking-[0.04em] text-[var(--fg-3)]"
                >
                  Correo corporativo
                </Label>
                <Input
                  id="edit-email"
                  type="email"
                  value={user.email}
                  disabled
                  className="bg-[var(--bg-muted)] text-[var(--fg-3)]"
                />
                <p className="text-[11px] text-[var(--fg-3)]">
                  El correo no puede modificarse.
                </p>
              </div>
            </div>

            {canEditRole && (
              <div className="grid gap-1.5">
                <Label className="text-xs font-semibold uppercase tracking-[0.04em] text-[var(--fg-3)]">
                  Rol del usuario
                </Label>
                <RolePicker value={role} onChange={setRole} name="edit-role" />
              </div>
            )}

            <div className="flex items-start gap-3 rounded-xl bg-white p-3 ring-1 ring-[rgba(195,198,215,0.30)]">
              <input
                id="edit-active"
                type="checkbox"
                checked={isActive}
                onChange={(e) => setIsActive(e.target.checked)}
                className="mt-0.5 size-4 rounded border-input"
              />
              <div className="flex-1">
                <Label
                  htmlFor="edit-active"
                  className="text-sm font-semibold text-[var(--fg-1)]"
                >
                  Cuenta activa
                </Label>
                <p className="text-[11.5px] text-[var(--fg-3)]">
                  Si la desactiva, el usuario no podrá iniciar sesión hasta que
                  se reactive.
                </p>
              </div>
            </div>

            {/* Live diff */}
            {hasChanges && (
              <div className="rounded-xl border border-[rgba(0,74,198,0.20)] bg-[var(--bg-accent)]/25 p-3.5">
                <div className="sd-meta mb-2 text-[var(--primary)]">
                  Cambios pendientes ({diff.length})
                </div>
                <div className="flex flex-col gap-1.5">
                  {diff.map((d) => (
                    <div
                      key={d.key}
                      className="flex flex-wrap items-center gap-2 text-[12.5px]"
                    >
                      <span className="min-w-[60px] font-mono text-[var(--fg-3)]">
                        {d.key}
                      </span>
                      <span className="font-mono text-[#93000a] line-through">
                        {d.from}
                      </span>
                      <ChevronRight className="size-3 text-[var(--fg-3)]" />
                      <span className="font-mono font-semibold text-[#065f46]">
                        {d.to}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Reset password (admin only) */}
            {isAdmin && (
              <div className="rounded-xl bg-white p-3.5 ring-1 ring-[rgba(195,198,215,0.30)]">
                <div className="flex items-center gap-3">
                  <span className="inline-flex size-8 items-center justify-center rounded-lg bg-[var(--bg-accent)] text-[var(--primary)]">
                    <KeyRound className="size-4" />
                  </span>
                  <div className="flex-1">
                    <div className="text-sm font-semibold text-[var(--fg-1)]">
                      Resetear contraseña
                    </div>
                    <p className="text-[11.5px] text-[var(--fg-3)]">
                      Asigna una nueva contraseña al usuario. Compártala por un
                      canal seguro.
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setShowPasswordReset((v) => !v);
                      setNewPassword("");
                      setConfirmPassword("");
                    }}
                  >
                    {showPasswordReset ? "Cancelar" : "Resetear"}
                  </Button>
                </div>

                {showPasswordReset && (
                  <div className="mt-3 grid gap-3 border-t border-[rgba(195,198,215,0.30)] pt-3">
                    <div className="grid gap-1.5">
                      <Label
                        htmlFor="reset-new-password"
                        className="text-xs font-semibold uppercase tracking-[0.04em] text-[var(--fg-3)]"
                      >
                        Nueva contraseña
                      </Label>
                      <Input
                        id="reset-new-password"
                        type="password"
                        value={newPassword}
                        onChange={(e) => setNewPassword(e.target.value)}
                        placeholder="Mínimo 8 caracteres"
                        minLength={8}
                      />
                    </div>

                    <div className="grid gap-1.5">
                      <Label
                        htmlFor="reset-confirm-password"
                        className="text-xs font-semibold uppercase tracking-[0.04em] text-[var(--fg-3)]"
                      >
                        Confirmar nueva contraseña
                      </Label>
                      <Input
                        id="reset-confirm-password"
                        type="password"
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        placeholder="Repita la nueva contraseña"
                        minLength={8}
                      />
                    </div>

                    <Button
                      type="button"
                      variant="destructive"
                      size="sm"
                      disabled={resetPasswordMutation.isPending}
                      onClick={handleResetPassword}
                    >
                      {resetPasswordMutation.isPending ? (
                        <>
                          <LoaderCircle className="mr-2 size-4 animate-spin" />
                          Reseteando...
                        </>
                      ) : (
                        "Confirmar reseteo"
                      )}
                    </Button>
                  </div>
                )}
              </div>
            )}
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancelar
            </Button>
            <Button
              type="submit"
              disabled={updateMutation.isPending || !hasChanges}
              className="bg-gradient-to-br from-[#004ac6] to-[#2563eb] font-semibold text-white shadow-[var(--shadow-brand-sm)] hover:shadow-[var(--shadow-brand-md)] disabled:opacity-60"
            >
              {updateMutation.isPending ? (
                <>
                  <LoaderCircle className="mr-2 size-4 animate-spin" />
                  Guardando...
                </>
              ) : (
                <>
                  <Check className="mr-2 size-4" />
                  Guardar cambios
                </>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
