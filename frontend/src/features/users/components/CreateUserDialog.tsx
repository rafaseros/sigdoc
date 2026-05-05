import { useState } from "react";
import { toast } from "sonner";
import {
  Check,
  FileEdit,
  Info,
  LoaderCircle,
  ShieldCheck,
  Sparkles,
  UserPlus,
} from "lucide-react";
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
import type { Role } from "@/shared/lib/permissions";
import { useCreateUser } from "../api";

type RoleOption = {
  value: Role;
  label: string;
  desc: string;
  icon: React.ReactNode;
};

const ROLE_OPTIONS: RoleOption[] = [
  {
    value: "admin",
    label: "Administrador",
    desc: "Acceso total. Puede crear, editar y desactivar usuarios, gestionar plantillas y ver auditoría.",
    icon: <ShieldCheck className="size-3.5" />,
  },
  {
    value: "template_creator",
    label: "Creador de plantillas",
    desc: "Sube y edita plantillas .docx, comparte con el equipo y genera documentos.",
    icon: <FileEdit className="size-3.5" />,
  },
  {
    value: "document_generator",
    label: "Generador",
    desc: "Solo puede generar documentos a partir de plantillas compartidas con su cuenta.",
    icon: <Sparkles className="size-3.5" />,
  },
];

export function RolePicker({
  value,
  onChange,
  name = "role",
}: {
  value: Role;
  onChange: (next: Role) => void;
  name?: string;
}) {
  return (
    <div className="grid gap-2.5 sm:grid-cols-3">
      {ROLE_OPTIONS.map((opt) => {
        const active = value === opt.value;
        return (
          <label
            key={opt.value}
            className={`relative flex cursor-pointer flex-col gap-1.5 rounded-xl bg-white p-3 ring-1 transition-all ${
              active
                ? "ring-2 ring-[var(--primary)] shadow-[var(--shadow-brand-sm)]"
                : "ring-[rgba(195,198,215,0.45)] hover:ring-[rgba(37,99,235,0.30)]"
            }`}
          >
            <input
              type="radio"
              name={name}
              value={opt.value}
              checked={active}
              onChange={() => onChange(opt.value)}
              className="pointer-events-none absolute opacity-0"
            />
            <div className="flex items-center gap-2">
              <span
                className={`inline-flex size-7 items-center justify-center rounded-lg ${
                  active
                    ? "bg-gradient-to-br from-[#004ac6] to-[#2563eb] text-white"
                    : "bg-[var(--bg-accent)] text-[var(--primary)]"
                }`}
              >
                {opt.icon}
              </span>
              <span className="flex-1 text-sm font-semibold text-[var(--fg-1)]">
                {opt.label}
              </span>
              <span
                className={`flex size-4 items-center justify-center rounded-full border ${
                  active
                    ? "border-[var(--primary)] bg-[var(--primary)] text-white"
                    : "border-[rgba(195,198,215,0.6)] bg-white"
                }`}
              >
                {active && <Check className="size-2.5" />}
              </span>
            </div>
            <p className="text-[11.5px] leading-snug text-[var(--fg-3)]">
              {opt.desc}
            </p>
          </label>
        );
      })}
    </div>
  );
}

export function CreateUserDialog() {
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<Role>("document_generator");

  const createMutation = useCreateUser();

  function resetForm() {
    setEmail("");
    setFullName("");
    setPassword("");
    setRole("document_generator");
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
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) resetForm();
      }}
    >
      <DialogTrigger
        render={
          <Button className="bg-gradient-to-br from-[#004ac6] to-[#2563eb] font-semibold text-white shadow-[var(--shadow-brand-sm)] hover:shadow-[var(--shadow-brand-md)]" />
        }
      >
        <UserPlus className="mr-2 size-4" />
        Crear Usuario
      </DialogTrigger>
      <DialogContent className="max-h-[88vh] overflow-y-auto sm:max-w-2xl">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle className="text-xl font-bold tracking-tight">
              Crear nuevo usuario
            </DialogTitle>
            <DialogDescription>
              Complete los datos para crear una nueva cuenta. La contraseña
              inicial se entregará al usuario para que la cambie en el primer
              ingreso.
            </DialogDescription>
          </DialogHeader>

          <div className="flex flex-col gap-4 py-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="grid gap-1.5">
                <Label htmlFor="user-fullname" className="text-xs font-semibold uppercase tracking-[0.04em] text-[var(--fg-3)]">
                  Nombre completo
                </Label>
                <Input
                  id="user-fullname"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Ej. María López Vargas"
                  required
                  autoFocus
                />
                <p className="text-[11px] text-[var(--fg-3)]">
                  Como aparecerá en documentos y auditoría.
                </p>
              </div>

              <div className="grid gap-1.5">
                <Label htmlFor="user-email" className="text-xs font-semibold uppercase tracking-[0.04em] text-[var(--fg-3)]">
                  Correo corporativo
                </Label>
                <Input
                  id="user-email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="usuario@ejemplo.com"
                  required
                />
                <p className="text-[11px] text-[var(--fg-3)]">
                  Será el identificador único de la cuenta.
                </p>
              </div>
            </div>

            <div className="grid gap-1.5">
              <Label className="text-xs font-semibold uppercase tracking-[0.04em] text-[var(--fg-3)]">
                Rol del usuario
              </Label>
              <RolePicker value={role} onChange={setRole} />
            </div>

            <div className="grid gap-1.5">
              <Label htmlFor="user-password" className="text-xs font-semibold uppercase tracking-[0.04em] text-[var(--fg-3)]">
                Contraseña inicial
              </Label>
              <Input
                id="user-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Mínimo 6 caracteres"
                required
                minLength={6}
              />
              <p className="text-[11px] text-[var(--fg-3)]">
                Comparta esta contraseña por un canal seguro. El usuario podrá
                cambiarla desde su perfil.
              </p>
            </div>

            <div className="flex items-start gap-2 rounded-[10px] bg-[var(--bg-accent)]/50 px-3.5 py-3 text-[13px] leading-[1.45] text-[var(--primary)]">
              <Info className="mt-0.5 size-4 shrink-0" />
              <span>
                El rol seleccionado aplicará una vez creada la cuenta.
                Podrá ajustarlo después desde la edición del usuario.
              </span>
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
            <Button
              type="submit"
              disabled={createMutation.isPending}
              className="bg-gradient-to-br from-[#004ac6] to-[#2563eb] font-semibold text-white shadow-[var(--shadow-brand-sm)] hover:shadow-[var(--shadow-brand-md)]"
            >
              {createMutation.isPending ? (
                <>
                  <LoaderCircle className="mr-2 size-4 animate-spin" />
                  Creando...
                </>
              ) : (
                <>
                  <UserPlus className="mr-2 size-4" />
                  Crear usuario
                </>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
