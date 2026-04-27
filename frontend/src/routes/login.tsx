import { createFileRoute, redirect, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { useAuth } from "@/shared/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-[#f7f9fb] to-[#e0e7ff]">
      <Card className="w-full max-w-sm border-0 bg-white/80 backdrop-blur-xl shadow-[0_12px_32px_rgba(25,28,30,0.06)]">
        <CardHeader className="space-y-1 pb-2 pt-8 px-8">
          <CardTitle className="text-3xl font-bold tracking-tight text-[#004ac6]">SigDoc</CardTitle>
          <CardDescription className="text-[#434655]">Inicie sesión para gestionar sus plantillas</CardDescription>
        </CardHeader>
        <CardContent className="px-8 pb-8">
          <form onSubmit={handleSubmit} className="space-y-5">
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
              <div className="flex items-center justify-between">
                <Label htmlFor="password" className="text-[#434655] font-medium">Contraseña</Label>
              </div>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="bg-[#e6e8ea] border-transparent focus:border-[#2563eb] focus:ring-[#2563eb]/20 transition-all"
              />
            </div>
            <Button
              type="submit"
              className="w-full bg-gradient-to-br from-[#004ac6] to-[#2563eb] text-white font-semibold shadow-[0_4px_12px_rgba(0,74,198,0.3)] hover:shadow-[0_6px_20px_rgba(0,74,198,0.4)] transition-all"
              disabled={loading}
            >
              {loading ? "Iniciando sesión..." : "Iniciar sesión"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
