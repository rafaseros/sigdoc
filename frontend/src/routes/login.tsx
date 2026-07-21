import { createFileRoute, redirect, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import {
  Calculator,
  Eye,
  FileText,
  Layers,
  Link2,
  LoaderCircle,
  LogIn,
  MousePointerClick,
  Sparkles,
} from "lucide-react";
import { useAuth } from "@/shared/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { ChangelogDialog } from "@/components/ChangelogDialog";
import { APP_VERSION } from "@/shared/version";

export const Route = createFileRoute("/login")({
  beforeLoad: () => {
    if (localStorage.getItem("access_token")) {
      throw redirect({ to: "/templates" });
    }
  },
  component: LoginPage,
});

/** Summarized capability list — icon + a few words each, only shipped features. */
const FEATURES = [
  { icon: FileText, label: "Plantillas Word con variables" },
  { icon: Layers, label: "Generación individual y masiva" },
  { icon: Link2, label: "Documentos relacionados que comparten variables" },
  { icon: MousePointerClick, label: "Plantillas desde un documento ejemplo" },
  { icon: Eye, label: "Vista previa y exportación a PDF" },
  { icon: Calculator, label: "Datos guardados y variables calculadas" },
] as const;

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [changelogOpen, setChangelogOpen] = useState(false);

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
      {/* Brand / marketing panel (desktop only — the form stacks first on mobile) */}
      <aside className="sd-brand-panel hidden flex-col justify-between p-14 lg:flex">
        <div className="flex items-center gap-2.5">
          <span className="inline-flex h-9 w-9 items-center justify-center rounded-[10px] bg-white text-[17px] font-bold tracking-tight text-[#004ac6]">
            S
          </span>
          <span className="text-[21px] font-bold tracking-tight">SigDoc</span>
        </div>

        <div className="max-w-[460px]">
          <div className="mb-3.5 text-[13px] font-semibold uppercase tracking-[0.08em] text-white/65">
            Sistema integrado de gestión de documentos
          </div>
          <h1 className="m-0 mb-3 text-[38px] font-bold leading-[1.12] tracking-[-0.025em]">
            Genere documentos perfectos desde plantillas Word.
          </h1>
          <p className="m-0 mb-7 max-w-[420px] text-[15px] leading-[1.5] text-white/80">
            Suba sus plantillas una vez y genere documentos siempre
            consistentes, con auditoría completa.
          </p>

          <ul className="m-0 flex list-none flex-col gap-2.5 p-0">
            {FEATURES.map(({ icon: Icon, label }) => (
              <li
                key={label}
                className="flex items-center gap-2.5 text-[13.5px] text-white/85"
              >
                <span className="inline-flex size-6 shrink-0 items-center justify-center rounded-md bg-white/15">
                  <Icon className="size-3.5" />
                </span>
                {label}
              </li>
            ))}
          </ul>
        </div>

        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-white/65">
          <span className="inline-flex items-center rounded-full bg-white/15 px-2 py-0.5 font-mono text-[11px] font-semibold text-white">
            v{APP_VERSION}
          </span>
          <button
            type="button"
            onClick={() => setChangelogOpen(true)}
            className="inline-flex items-center gap-1.5 rounded-sm text-white/80 underline-offset-2 transition-colors hover:text-white hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/60"
          >
            <Sparkles className="size-3.5" />
            Novedades
          </button>
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

          {/* Mobile-only version + changelog access (the brand panel is hidden) */}
          <div className="mt-4 flex items-center justify-center gap-3 lg:hidden">
            <span className="inline-flex items-center rounded-full border border-[rgba(195,198,215,0.40)] px-2 py-0.5 font-mono text-[11px] font-medium text-[var(--fg-3)]">
              v{APP_VERSION}
            </span>
            <button
              type="button"
              onClick={() => setChangelogOpen(true)}
              className="inline-flex items-center gap-1.5 rounded-sm text-xs font-medium text-[var(--primary)] underline-offset-2 transition-colors hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
            >
              <Sparkles className="size-3.5" />
              Novedades
            </button>
          </div>
        </div>
      </main>

      <ChangelogDialog open={changelogOpen} onOpenChange={setChangelogOpen} />
    </div>
  );
}
