import { useState } from "react";
import { toast } from "sonner";
import { UserPlusIcon } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useCreateUser } from "../api";

export function CreateUserDialog() {
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");

  const createMutation = useCreateUser();

  function resetForm() {
    setEmail("");
    setFullName("");
    setPassword("");
  }

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

    if (password.length < 6) {
      toast.error("La contraseña debe tener al menos 6 caracteres");
      return;
    }

    try {
      await createMutation.mutateAsync({
        email: email.trim(),
        full_name: fullName.trim(),
        password,
      });
      toast.success("Usuario creado con éxito");
      resetForm();
      setOpen(false);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Error al crear usuario";
      toast.error(message);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button />}>
        <UserPlusIcon className="size-4 mr-2" />
        Crear Usuario
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Crear Usuario</DialogTitle>
            <DialogDescription>
              Complete los datos para crear un nuevo usuario.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="user-email">Email *</Label>
              <Input
                id="user-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="usuario@ejemplo.com"
                required
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="user-fullname">Nombre Completo *</Label>
              <Input
                id="user-fullname"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Juan Pérez"
                required
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="user-password">Contraseña *</Label>
              <Input
                id="user-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Mínimo 6 caracteres"
                required
                minLength={6}
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                resetForm();
                setOpen(false);
              }}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={createMutation.isPending}>
              {createMutation.isPending ? "Creando..." : "Crear"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
