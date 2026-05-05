import { createFileRoute, redirect, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { LoaderCircle, LogIn } from "lucide-react";
import { useAuth } from "@/shared/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";

export const Route = createFileRoute("/login")({
  beforeLoad: () => {
    if (localStorage.getItem("access_token")) {
      throw redirect({ to: "/templates" });
    }
  },
  component: LoginPage,
});

function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await login(email, password);
      toast.success("Inicio de sesión exitoso");
      navigate({ to: "/templates" });
    } catch {
      toast.error("Credenciales inválidas");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid min-h-screen lg:grid-cols-[1.1fr_1fr]">
      {/* Brand panel (desktop) */}
      <aside className="sd-brand-panel hidden lg:flex flex-col justify-between p-14">
        <div className="flex items-center gap-2.5">
          <span className="inline-flex h-9 w-9 items-center justify-center rounded-[10px] bg-white text-[17px] font-bold text-[#004ac6] tracking-tight">
            S
          </span>
          <span className="text-[21px] font-bold tracking-tight">SigDoc</span>
        </div>

        <div className="max-w-[460px]">
          <div className="mb-3.5 text-[13px] font-semibold uppercase tracking-[0.08em] text-white/65">
            Sistema integrado de gestión de documentos
          </div>
          <h1 className="m-0 mb-3.5 text-[42px] font-bold leading-[1.1] tracking-[-0.025em]">
            Sus contratos,<br />sin trabajo manual.
          </h1>
          <p className="m-0 max-w-[420px] text-[15px] leading-[1.5] text-white/80">
            Suba plantillas .docx con marcadores variables y genere documentos legales en bloque, con auditoría completa.
          </p>
        </div>

        <div className="flex gap-6 text-xs text-white/65">
          <span>v1.4 · estable</span>
          <span>Soporte: devrafaseros@gmail.com</span>
        </div>
      </aside>

      {/* Form panel */}
      <main className="flex items-center justify-center p-6 lg:p-8">
        <div className="w-full max-w-sm">
          {/* Mobile logo */}
          <div className="mb-8 flex items-center gap-2.5 lg:hidden">
            <span className="inline-flex h-9 w-9 items-center justify-center rounded-[10px] bg-gradient-to-br from-[#004ac6] to-[#2563eb] text-[17px] font-bold text-white shadow-[var(--shadow-brand-sm)]">
              S
            </span>
            <span className="text-xl font-bold tracking-tight text-[#004ac6]">SigDoc</span>
          </div>

          <h2 className="m-0 text-[26px] font-bold tracking-[-0.02em]">Iniciar sesión</h2>
          <p className="mt-1.5 mb-6 text-[13.5px] text-[var(--fg-3)]">
            Acceda con su cuenta corporativa.
          </p>

          <form onSubmit={handleSubmit} className="flex flex-col gap-3.5">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="email" className="text-[12.5px] font-medium text-[var(--fg-2)]">
                Correo electrónico
              </Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoFocus
                autoComplete="email"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="password" className="text-[12.5px] font-medium text-[var(--fg-2)]">
                Contraseña
              </Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
              />
            </div>

            <Button
              type="submit"
              disabled={loading}
              className="mt-2 h-10 bg-gradient-to-br from-[#004ac6] to-[#2563eb] font-semibold text-white shadow-[var(--shadow-brand-sm)] hover:shadow-[var(--shadow-brand-md)]"
            >
              {loading ? (
                <>
                  <LoaderCircle className="size-4 animate-spin" />
                  Iniciando sesión…
                </>
              ) : (
                <>
                  <LogIn className="size-4" />
                  Iniciar sesión
                </>
              )}
            </Button>
          </form>

          <div className="mt-5 text-center text-xs text-[var(--fg-3)]">
            ¿No tiene cuenta? Contacte a su administrador.
          </div>
        </div>
      </main>
    </div>
  );
}
