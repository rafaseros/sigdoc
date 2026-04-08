import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/shared/lib/api-client";

export function VerificationBanner() {
  const [loading, setLoading] = useState(false);

  async function handleResend() {
    setLoading(true);
    try {
      await apiClient.post("/auth/resend-verification");
      toast.success("Correo de verificación reenviado. Revisá tu bandeja de entrada.");
    } catch {
      toast.error("No se pudo reenviar el correo. Intentá de nuevo más tarde.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-amber-50 border-b border-amber-200">
      <div className="container mx-auto px-4 py-2.5 flex items-center justify-between gap-4">
        <p className="text-sm text-amber-800 font-medium">
          Tu correo electrónico no ha sido verificado. Revisá tu bandeja de entrada.
        </p>
        <Button
          size="sm"
          variant="outline"
          onClick={handleResend}
          disabled={loading}
          className="shrink-0 border-amber-400 text-amber-800 hover:bg-amber-100 hover:text-amber-900 bg-transparent"
        >
          {loading ? "Enviando..." : "Reenviar correo de verificación"}
        </Button>
      </div>
    </div>
  );
}
