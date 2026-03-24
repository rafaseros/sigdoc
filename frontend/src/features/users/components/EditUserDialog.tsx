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
import { useUpdateUser, type UserResponse } from "../api";

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
  const [email, setEmail] = useState(user.email);
  const [fullName, setFullName] = useState(user.full_name);
  const [isActive, setIsActive] = useState(user.is_active);

  const updateMutation = useUpdateUser();

  useEffect(() => {
    setEmail(user.email);
    setFullName(user.full_name);
    setIsActive(user.is_active);
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
      });
      toast.success("Usuario actualizado con éxito");
      onOpenChange(false);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Error al actualizar usuario";
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
