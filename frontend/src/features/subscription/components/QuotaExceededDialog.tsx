import { useState, useEffect } from "react";
import { AlertCircleIcon } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

// ─── Event contract ─────────────────────────────────────────────────────────
// The api-client interceptor dispatches a "quota:exceeded" CustomEvent on
// window with this detail shape. The dialog listens and shows itself.

export interface QuotaExceededDetail {
  error: string;
  limit_type: string;
  limit_value: number | null;
  current_usage: number;
  tier_name: string;
}

export const QUOTA_EXCEEDED_EVENT = "quota:exceeded";

// ─── Helpers ─────────────────────────────────────────────────────────────────

const RESOURCE_LABELS: Record<string, string> = {
  documents: "documentos mensuales",
  templates: "plantillas",
  users: "usuarios",
  bulk_generation: "generación masiva",
  template_shares: "compartidos de plantilla",
};

function formatResourceLabel(limitType: string): string {
  return RESOURCE_LABELS[limitType] ?? limitType;
}

// ─── Component ───────────────────────────────────────────────────────────────

export function QuotaExceededDialog() {
  const [open, setOpen] = useState(false);
  const [detail, setDetail] = useState<QuotaExceededDetail | null>(null);

  useEffect(() => {
    function handleEvent(e: Event) {
      const custom = e as CustomEvent<QuotaExceededDetail>;
      setDetail(custom.detail);
      setOpen(true);
    }

    window.addEventListener(QUOTA_EXCEEDED_EVENT, handleEvent);
    return () => window.removeEventListener(QUOTA_EXCEEDED_EVENT, handleEvent);
  }, []);

  if (!detail) return null;

  const resourceLabel = formatResourceLabel(detail.limit_type);
  const limitText =
    detail.limit_value !== null
      ? `${detail.limit_value} ${resourceLabel}`
      : resourceLabel;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="sm:max-w-md" showCloseButton>
        <DialogHeader>
          <div className="flex items-center gap-2">
            <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-[#ffdad6]">
              <AlertCircleIcon className="size-5 text-[#ba1a1a]" />
            </div>
            <DialogTitle>Límite alcanzado</DialogTitle>
          </div>
          <DialogDescription>
            Tu plan <strong>{detail.tier_name}</strong> tiene un límite de{" "}
            <strong>{limitText}</strong>. Ya usaste{" "}
            <strong>{detail.current_usage}</strong> este mes.
          </DialogDescription>
        </DialogHeader>

        <div className="rounded-lg bg-[#fff8f7] border border-[#ffdad6] p-3 text-sm text-[#ba1a1a]">
          <p className="font-medium">¿Qué hacer?</p>
          <p className="mt-1 text-[#434655]">
            Contactá al administrador de tu organización para actualizar al plan
            Pro o Enterprise y obtener límites más altos.
          </p>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => setOpen(false)}
            className="border-[rgba(195,198,215,0.3)] text-[#434655]"
          >
            Cerrar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
