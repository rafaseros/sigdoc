import { createFileRoute, Link, redirect, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { useAuth } from "@/shared/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "sonner";
import axios from "axios";

export const Route = createFileRoute("/signup")({
  beforeLoad: () => {
    if (localStorage.getItem("access_token")) {
      throw redirect({ to: "/templates" });
    }
  },
  component: SignupPage,
});

function SignupPage() {
  const { signup } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [organizationName, setOrganizationName] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (password.length < 8) {
      toast.error("La contraseña debe tener al menos 8 caracteres");
      return;
    }

    setLoading(true);
    try {
      await signup(email, password, fullName, organizationName);
      toast.success("¡Bienvenido a SigDoc!");
      navigate({ to: "/templates" });
    } catch (err) {
      if (axios.isAxiosError(err)) {
        const status = err.response?.status;
        const detail = err.response?.data?.detail;

        if (status === 409) {
          if (typeof detail === "string" && detail.toLowerCase().includes("email")) {
            toast.error("El correo electrónico ya está registrado");
          } else if (typeof detail === "string" && detail.toLowerCase().includes("organization")) {
            toast.error("El nombre de la organización ya está en uso");
          } else {
            toast.error(detail ?? "El registro no pudo completarse");
          }
        } else if (status === 429) {
          toast.error("Demasiados intentos. Intente más tarde");
        } else {
          toast.error("Error al registrarse. Intente de nuevo");
        }
      } else {
        toast.error("Error al registrarse. Intente de nuevo");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-[#f7f9fb] to-[#e0e7ff]">
      <Card className="w-full max-w-sm border-0 bg-white/80 backdrop-blur-xl shadow-[0_12px_32px_rgba(25,28,30,0.06)]">
        <CardHeader className="space-y-1 pb-2 pt-8 px-8">
          <CardTitle className="text-3xl font-bold tracking-tight text-[#004ac6]">SigDoc</CardTitle>
          <CardDescription className="text-[#434655]">Cree su cuenta para comenzar</CardDescription>
        </CardHeader>
        <CardContent className="px-8 pb-8">
          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="fullName" className="text-[#434655] font-medium">Nombre completo</Label>
              <Input
                id="fullName"
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                required
                className="bg-[#e6e8ea] border-transparent focus:border-[#2563eb] focus:ring-[#2563eb]/20 transition-all"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="organizationName" className="text-[#434655] font-medium">Nombre de la organización</Label>
              <Input
                id="organizationName"
                type="text"
                value={organizationName}
                onChange={(e) => setOrganizationName(e.target.value)}
                required
                className="bg-[#e6e8ea] border-transparent focus:border-[#2563eb] focus:ring-[#2563eb]/20 transition-all"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email" className="text-[#434655] font-medium">Correo electrónico</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="bg-[#e6e8ea] border-transparent focus:border-[#2563eb] focus:ring-[#2563eb]/20 transition-all"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password" className="text-[#434655] font-medium">
                Contraseña
                <span className="ml-1 text-xs text-[#7a7e99] font-normal">(mínimo 8 caracteres)</span>
              </Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
                className="bg-[#e6e8ea] border-transparent focus:border-[#2563eb] focus:ring-[#2563eb]/20 transition-all"
              />
            </div>
            <Button
              type="submit"
              className="w-full bg-gradient-to-br from-[#004ac6] to-[#2563eb] text-white font-semibold shadow-[0_4px_12px_rgba(0,74,198,0.3)] hover:shadow-[0_6px_20px_rgba(0,74,198,0.4)] transition-all"
              disabled={loading}
            >
              {loading ? "Creando cuenta..." : "Crear cuenta"}
            </Button>
          </form>
          <p className="mt-6 text-center text-sm text-[#7a7e99]">
            ¿Ya tiene cuenta?{" "}
            <Link to="/login" className="text-[#2563eb] font-medium hover:underline">
              Inicie sesión
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
