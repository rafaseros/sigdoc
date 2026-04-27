import { useState, useEffect } from "react";
import { toast } from "sonner";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useUpdateUser, useResetUserPassword, type UserResponse } from "../api";
import { useAuth } from "@/shared/lib/auth";
import { ROLE_LABELS } from "@/shared/lib/role-labels";

interface EditUserDialogProps {
  user: UserResponse;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function EditUserDialog({
  user,
  open,
  onOpenChange,
}: EditUserDialogProps) {
  const { user: currentUser } = useAuth();
  const [email, setEmail] = useState(user.email);
  const [fullName, setFullName] = useState(user.full_name);
  const [isActive, setIsActive] = useState(user.is_active);
  const [role, setRole] = useState(user.role);

  const [showPasswordReset, setShowPasswordReset] = useState(false);
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const updateMutation = useUpdateUser();
  const resetPasswordMutation = useResetUserPassword();

  const isAdmin = currentUser?.role === "admin";
  const isEditingSelf = currentUser?.id === user.id;
  const canEditRole = isAdmin && !isEditingSelf;

  useEffect(() => {
    setEmail(user.email);
    setFullName(user.full_name);
    setIsActive(user.is_active);
    setRole(user.role);
    setShowPasswordReset(false);
    setNewPassword("");
    setConfirmPassword("");
  }, [user]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailPattern.test(email)) {
      toast.error("Ingrese un email válido");
      return;
    }

    if (!fullName.trim()) {
      toast.error("El nombre completo es obligatorio");
      return;
    }

    try {
      await updateMutation.mutateAsync({
        id: user.id,
        email: email.trim(),
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

  async function handleResetPassword(e: React.FormEvent) {
    e.preventDefault();

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
      <DialogContent className="sm:max-w-md">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Editar Usuario</DialogTitle>
            <DialogDescription>
              Modifique los datos del usuario.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="edit-email">Email *</Label>
              <Input
                id="edit-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="usuario@ejemplo.com"
                required
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="edit-fullname">Nombre Completo *</Label>
              <Input
                id="edit-fullname"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Juan Pérez"
                required
              />
            </div>

            {canEditRole && (
              <div className="grid gap-2">
                <Label htmlFor="edit-role">Rol</Label>
                <Select value={role} onValueChange={(v) => setRole(v ?? "document_generator")}>
                  <SelectTrigger id="edit-role">
                    <SelectValue placeholder="Seleccionar rol" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="admin">{ROLE_LABELS.admin}</SelectItem>
                    <SelectItem value="template_creator">{ROLE_LABELS.template_creator}</SelectItem>
                    <SelectItem value="document_generator">{ROLE_LABELS.document_generator}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            )}

            <div className="flex items-center gap-2">
              <input
                id="edit-active"
                type="checkbox"
                checked={isActive}
                onChange={(e) => setIsActive(e.target.checked)}
                className="size-4 rounded border-input"
              />
              <Label htmlFor="edit-active">Usuario activo</Label>
            </div>

            {isAdmin && (
              <div className="border-t pt-3 grid gap-3">
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
                  {showPasswordReset
                    ? "Cancelar reseteo"
                    : "Resetear contraseña"}
                </Button>

                {showPasswordReset && (
                  <div className="grid gap-3">
                    <div className="grid gap-2">
                      <Label htmlFor="reset-new-password">
                        Nueva contraseña *
                      </Label>
                      <Input
                        id="reset-new-password"
                        type="password"
                        value={newPassword}
                        onChange={(e) => setNewPassword(e.target.value)}
                        placeholder="Mínimo 8 caracteres"
                        minLength={8}
                        required
                      />
                    </div>

                    <div className="grid gap-2">
                      <Label htmlFor="reset-confirm-password">
                        Confirmar nueva contraseña *
                      </Label>
                      <Input
                        id="reset-confirm-password"
                        type="password"
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        placeholder="Repita la nueva contraseña"
                        minLength={8}
                        required
                      />
                    </div>

                    <Button
                      type="button"
                      variant="destructive"
                      size="sm"
                      disabled={resetPasswordMutation.isPending}
                      onClick={handleResetPassword}
                    >
                      {resetPasswordMutation.isPending
                        ? "Reseteando..."
                        : "Confirmar reseteo"}
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
            <Button type="submit" disabled={updateMutation.isPending}>
              {updateMutation.isPending ? "Guardando..." : "Guardar"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
