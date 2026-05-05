import { useState } from "react";
import { Trash2, Share2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

import { useTemplateShares } from "../api/queries";
import { useUnshareTemplate } from "../api/mutations";
import { ShareTemplateDialog } from "./ShareTemplateDialog";

interface SharesTabProps {
  templateId: string;
  templateName: string;
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("es-ES", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function getInitials(email: string): string {
  const local = email.split("@")[0];
  const parts = local.split(/[._-]/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return local.slice(0, 2).toUpperCase();
}

export function SharesTab({ templateId, templateName }: SharesTabProps) {
  const { data: shares, isLoading, isError, error } = useTemplateShares(templateId);
  const unshareTemplate = useUnshareTemplate();
  const [confirmRevokeId, setConfirmRevokeId] = useState<string | null>(null);
  const [shareDialogOpen, setShareDialogOpen] = useState(false);

  const handleRevoke = async (userId: string) => {
    try {
      await unshareTemplate.mutateAsync({ templateId, userId });
      toast.success("Acceso revocado con éxito");
    } catch (err: unknown) {
      const detail =
        err &&
        typeof err === "object" &&
        "response" in err &&
        (err as { response?: { data?: { detail?: string } } }).response?.data
          ?.detail;
      toast.error((detail as string) || "Error al revocar el acceso");
    } finally {
      setConfirmRevokeId(null);
    }
  };

  return (
    <div className="overflow-hidden rounded-xl bg-white shadow-[var(--shadow-md)]">
      <div className="flex items-center justify-between border-b border-[rgba(195,198,215,0.20)] px-5 py-4">
        <div>
          <h3 className="m-0 text-base font-bold tracking-tight text-[var(--fg-1)]">
            Compartido con
          </h3>
          <p className="mt-0.5 text-[12.5px] text-[var(--fg-3)]">
            Usuarios que pueden ver y generar desde esta plantilla.
          </p>
        </div>
        <Button
          size="sm"
          onClick={() => setShareDialogOpen(true)}
          className="bg-gradient-to-br from-[#004ac6] to-[#2563eb] font-semibold text-white shadow-[var(--shadow-brand-sm)] hover:shadow-[var(--shadow-brand-md)]"
        >
          <Share2 className="size-3.5" />
          Compartir
        </Button>
      </div>

      {isLoading ? (
        <div className="space-y-2 p-5">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      ) : isError ? (
        <div className="m-5 rounded-lg border border-destructive/50 bg-destructive/5 p-4 text-sm text-destructive">
          Error al cargar compartidos: {error?.message ?? "Error desconocido"}
        </div>
      ) : !shares || shares.length === 0 ? (
        <div className="flex flex-col items-center justify-center p-12 text-center">
          <p className="text-[var(--fg-2)]">
            Esta plantilla no se ha compartido con nadie.
          </p>
          <p className="mt-1 text-sm text-[var(--fg-3)]">
            Usá el botón <strong>Compartir</strong> arriba para agregar usuarios.
          </p>
        </div>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[rgba(195,198,215,0.20)] bg-[var(--bg-page)]">
              <th className="px-5 py-2.5 text-left text-[11px] font-semibold uppercase tracking-[0.04em] text-[var(--fg-3)]">
                Usuario
              </th>
              <th className="px-3 py-2.5 text-left text-[11px] font-semibold uppercase tracking-[0.04em] text-[var(--fg-3)]">
                Compartido el
              </th>
              <th className="w-[160px] px-3 py-2.5" />
            </tr>
          </thead>
          <tbody>
            {shares.map((share) => {
              const email = share.user_email ?? share.user_id;
              const isConfirming = confirmRevokeId === share.user_id;
              return (
                <tr
                  key={share.id}
                  className="border-b border-[rgba(195,198,215,0.15)] last:border-b-0 transition-colors hover:bg-[var(--bg-page)]"
                >
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-2.5">
                      <span className="inline-flex size-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-[#004ac6] to-[#2563eb] text-[10.5px] font-semibold text-white">
                        {getInitials(email)}
                      </span>
                      <span className="font-medium text-[var(--fg-1)]">{email}</span>
                    </div>
                  </td>
                  <td className="px-3 py-3 text-[var(--fg-3)]">
                    {share.shared_at ? formatDate(share.shared_at) : "—"}
                  </td>
                  <td className="px-3 py-3">
                    {isConfirming ? (
                      <div className="flex items-center gap-1.5">
                        <Button
                          size="sm"
                          disabled={unshareTemplate.isPending}
                          onClick={() => handleRevoke(share.user_id)}
                          className="bg-[var(--destructive)] font-semibold text-white hover:bg-[#93000a]"
                        >
                          {unshareTemplate.isPending ? "…" : "Confirmar"}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setConfirmRevokeId(null)}
                        >
                          No
                        </Button>
                      </div>
                    ) : (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-[var(--destructive)] hover:bg-[#ffdad6]/50 hover:text-[var(--destructive)]"
                        onClick={() => setConfirmRevokeId(share.user_id)}
                      >
                        <Trash2 className="size-3.5" />
                        Revocar
                      </Button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}

      <ShareTemplateDialog
        templateId={templateId}
        templateName={templateName}
        open={shareDialogOpen}
        onOpenChange={setShareDialogOpen}
      />
    </div>
  );
}
