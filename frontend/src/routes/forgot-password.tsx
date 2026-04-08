import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { apiClient } from "@/shared/lib/api-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export const Route = createFileRoute("/forgot-password")({
  component: ForgotPasswordPage,
});

function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await apiClient.post("/auth/forgot-password", { email });
    } catch {
      // Silently ignore errors — anti-enumeration: always show success
    } finally {
      setLoading(false);
      setSubmitted(true);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-[#f7f9fb] to-[#e0e7ff]">
      <Card className="w-full max-w-sm border-0 bg-white/80 backdrop-blur-xl shadow-[0_12px_32px_rgba(25,28,30,0.06)]">
        <CardHeader className="space-y-1 pb-2 pt-8 px-8">
          <CardTitle className="text-3xl font-bold tracking-tight text-[#004ac6]">SigDoc</CardTitle>
          <CardDescription className="text-[#434655]">Recuperar contraseña</CardDescription>
        </CardHeader>
        <CardContent className="px-8 pb-8">
          {submitted ? (
            <div className="space-y-4 text-center">
              <p className="text-sm text-[#434655]">
                Si el correo está registrado, recibirás un enlace para restablecer tu contraseña.
              </p>
              <Link
                to="/login"
                className="block text-sm text-[#2563eb] font-medium hover:underline"
              >
                Volver al inicio de sesión
              </Link>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-5">
              <div className="space-y-2">
                <Label htmlFor="email" className="text-[#434655] font-medium">
                  Correo electrónico
                </Label>
                <Input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  placeholder="usuario@ejemplo.com"
                  className="bg-[#e6e8ea] border-transparent focus:border-[#2563eb] focus:ring-[#2563eb]/20 transition-all"
                />
              </div>
              <Button
                type="submit"
                className="w-full bg-gradient-to-br from-[#004ac6] to-[#2563eb] text-white font-semibold shadow-[0_4px_12px_rgba(0,74,198,0.3)] hover:shadow-[0_6px_20px_rgba(0,74,198,0.4)] transition-all"
                disabled={loading}
              >
                {loading ? "Enviando..." : "Enviar enlace"}
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
