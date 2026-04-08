import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { apiClient } from "@/shared/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export const Route = createFileRoute("/verify-email")({
  component: VerifyEmailPage,
});

function VerifyEmailPage() {
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const search = new URLSearchParams(window.location.search);
  const token = search.get("token");

  useEffect(() => {
    if (!token) {
      setStatus("error");
      return;
    }

    apiClient
      .get(`/auth/verify-email?token=${encodeURIComponent(token)}`)
      .then(() => setStatus("success"))
      .catch(() => setStatus("error"));
  }, [token]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-[#f7f9fb] to-[#e0e7ff]">
      <Card className="w-full max-w-sm border-0 bg-white/80 backdrop-blur-xl shadow-[0_12px_32px_rgba(25,28,30,0.06)]">
        <CardHeader className="space-y-1 pb-2 pt-8 px-8">
          <CardTitle className="text-3xl font-bold tracking-tight text-[#004ac6]">SigDoc</CardTitle>
        </CardHeader>
        <CardContent className="px-8 pb-8">
          {status === "loading" && (
            <p className="text-[#434655] text-center">Verificando correo...</p>
          )}
          {status === "success" && (
            <div className="space-y-4 text-center">
              <div className="text-4xl">✓</div>
              <p className="text-[#434655] font-medium">Correo verificado exitosamente</p>
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
                El enlace de verificación es inválido o ha expirado
              </p>
              <Link
                to="/login"
                className="block text-sm text-[#2563eb] font-medium hover:underline"
              >
                Ir al inicio de sesión
              </Link>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
