import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { apiClient } from "@/shared/lib/api-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "sonner";

export const Route = createFileRoute("/reset-password")({
  component: ResetPasswordPage,
});

function ResetPasswordPage() {
  const search = new URLSearchParams(window.location.search);
  const token = search.get("token") ?? "";

  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<"idle" | "success" | "error">("idle");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (newPassword.length < 8) {
      toast.error("La contraseña debe tener al menos 8 caracteres");
      return;
    }

    if (newPassword !== confirmPassword) {
      toast.error("Las contraseñas no coinciden");
      return;
    }

    setLoading(true);
    try {
      await apiClient.post("/auth/reset-password", {
        token,
        new_password: newPassword,
      });
      setStatus("success");
    } catch {
      setStatus("error");
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-[#f7f9fb] to-[#e0e7ff]">
        <Card className="w-full max-w-sm border-0 bg-white/80 backdrop-blur-xl shadow-[0_12px_32px_rgba(25,28,30,0.06)]">
          <CardContent className="px-8 py-8 text-center space-y-4">
            <p className="text-[#434655] font-medium">
              El enlace es inválido o ha expirado
            </p>
            <Link to="/login" className="block text-sm text-[#2563eb] font-medium hover:underline">
              Volver al inicio de sesión
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-[#f7f9fb] to-[#e0e7ff]">
      <Card className="w-full max-w-sm border-0 bg-white/80 backdrop-blur-xl shadow-[0_12px_32px_rgba(25,28,30,0.06)]">
        <CardHeader className="space-y-1 pb-2 pt-8 px-8">
          <CardTitle className="text-3xl font-bold tracking-tight text-[#004ac6]">SigDoc</CardTitle>
          <CardDescription className="text-[#434655]">Restablecer contraseña</CardDescription>
        </CardHeader>
        <CardContent className="px-8 pb-8">
          {status === "success" && (
            <div className="space-y-4 text-center">
              <p className="text-[#434655] font-medium">
                Contraseña actualizada exitosamente
              </p>
              <Link
                to="/login"
                className="block text-sm text-[#2563eb] font-medium hover:underline"
              >
                Ir al inicio de sesión
              </Link>
            </div>
          )}
          {status === "error" && (
            <div className="space-y-4 text-center">
              <p className="text-[#434655] font-medium">
                El enlace es inválido o ha expirado
              </p>
              <Link
                to="/login"
                className="block text-sm text-[#2563eb] font-medium hover:underline"
              >
                Volver al inicio de sesión
              </Link>
            </div>
          )}
          {status === "idle" && (
            <form onSubmit={handleSubmit} className="space-y-5">
              <div className="space-y-2">
                <Label htmlFor="new-password" className="text-[#434655] font-medium">
                  Nueva contraseña
                  <span className="ml-1 text-xs text-[#7a7e99] font-normal">(mínimo 8 caracteres)</span>
                </Label>
                <Input
                  id="new-password"
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                  minLength={8}
                  className="bg-[#e6e8ea] border-transparent focus:border-[#2563eb] focus:ring-[#2563eb]/20 transition-all"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="confirm-password" className="text-[#434655] font-medium">
                  Confirmar contraseña
                </Label>
                <Input
                  id="confirm-password"
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
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
                {loading ? "Actualizando..." : "Actualizar contraseña"}
              </Button>
              <p className="text-center text-sm text-[#7a7e99]">
                <Link to="/login" className="text-[#2563eb] font-medium hover:underline">
                  Volver al inicio de sesión
                </Link>
              </p>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
