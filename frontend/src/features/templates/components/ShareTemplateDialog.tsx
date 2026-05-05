import { useState } from "react";
import { toast } from "sonner";
import { Share2, Trash2, UserPlus } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";

import { useTemplateShares } from "../api/queries";
import { useShareTemplate, useUnshareTemplate } from "../api/mutations";

interface ShareTemplateDialogProps {
  templateId: string;
  templateName: string;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}

function getInitials(email: string): string {
  const local = email.split("@")[0];
  const parts = local.split(/[._-]/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return local.slice(0, 2).toUpperCase();
}

export function ShareTemplateDialog({
  templateId,
  templateName,
  open: openProp,
  onOpenChange,
}: ShareTemplateDialogProps) {
  const isControlled = openProp !== undefined;
  const [internalOpen, setInternalOpen] = useState(false);
  const open = isControlled ? openProp : internalOpen;
  const setOpen = (v: boolean) => {
    if (isControlled) onOpenChange?.(v);
    else setInternalOpen(v);
  };
  const [email, setEmail] = useState("");

  const { data: shares, isLoading: sharesLoading } = useTemplateShares(templateId);
  const shareTemplate = useShareTemplate();
  const unshareTemplate = useUnshareTemplate();

  function handleShare() {
    const trimmedEmail = email.trim();
    if (!trimmedEmail) {
      toast.error("Ingrese el correo del usuario para compartir");
      return;
    }

    shareTemplate.mutate(
      { templateId, email: trimmedEmail },
      {
        onSuccess: () => {
          toast.success("Plantilla compartida con éxito");
          setEmail("");
        },
        onError: (err: unknown) => {
          const status =
            err && typeof err === "object" && "response" in err
              ? (err as { response?: { status?: number } }).response?.status
              : undefined;
          const detail =
            err && typeof err === "object" && "response" in err
              ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
              : undefined;

          if (status === 404) {
            toast.error("No se encontró un usuario con ese correo");
          } else if (status === 422 || status === 409) {
            toast.error("Esta plantilla ya fue compartida con ese usuario");
          } else {
            toast.error((detail as string) || "Error al compartir la plantilla");
          }
        },
      }
    );
  }

  function handleRevoke(userId: string) {
    unshareTemplate.mutate(
      { templateId, userId },
      {
        onSuccess: () => {
          toast.success("Acceso revocado con éxito");
        },
        onError: (err: unknown) => {
          const detail =
            err &&
            typeof err === "object" &&
            "response" in err &&
            (err as { response?: { data?: { detail?: string } } }).response?.data?.detail;
          toast.error((detail as string) || "Error al revocar el acceso");
        },
      }
    );
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      {!isControlled && (
        <DialogTrigger render={<Button variant="outline" />}>
          <Share2 className="size-4" />
          Compartir
        </DialogTrigger>
      )}

      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Compartir plantilla</DialogTitle>
          <DialogDescription>
            Comparta "{templateName}" con otros usuarios de su organización. Podrán ver y generar documentos, pero no modificar la plantilla.
          </DialogDescription>
        </DialogHeader>

        {/* Add new share */}
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="share-email" className="text-[12.5px] font-medium text-[var(--fg-2)]">
            Agregar usuario por correo
          </Label>
          <div className="flex gap-2">
            <Input
              id="share-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleShare();
              }}
              placeholder="correo@ejemplo.com"
              className="flex-1"
            />
            <Button
              onClick={handleShare}
              disabled={!email.trim() || shareTemplate.isPending}
              className="shrink-0 bg-gradient-to-br from-[#004ac6] to-[#2563eb] font-semibold text-white shadow-[var(--shadow-brand-sm)] hover:shadow-[var(--shadow-brand-md)]"
            >
              <UserPlus className="size-3.5" />
              {shareTemplate.isPending ? "Compartiendo…" : "Compartir"}
            </Button>
          </div>
        </div>

        {/* Current shares */}
        <div className="flex flex-col gap-2">
          <div className="sd-meta">
            Usuarios con acceso {shares ? `(${shares.length})` : ""}
          </div>
          {sharesLoading ? (
            <div className="flex flex-col gap-2">
              {Array.from({ length: 2 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : !shares || shares.length === 0 ? (
            <div className="rounded-lg border border-dashed border-[rgba(195,198,215,0.40)] p-4 text-center">
              <p className="m-0 text-sm text-[var(--fg-3)]">
                Esta plantilla aún no ha sido compartida con nadie.
              </p>
            </div>
          ) : (
            <div className="flex max-h-52 flex-col gap-1.5 overflow-y-auto">
              {shares.map((share) => {
                const userEmail = share.user_email ?? share.user_id;
                return (
                  <div
                    key={share.id}
                    className="flex items-center gap-2.5 rounded-lg bg-[var(--bg-page)] px-3 py-2 ring-1 ring-[rgba(195,198,215,0.20)]"
                  >
                    <span className="inline-flex size-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-[#004ac6] to-[#2563eb] text-[10.5px] font-semibold text-white">
                      {getInitials(userEmail)}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium text-[var(--fg-1)]">
                        {userEmail}
                      </div>
                      {share.shared_at && (
                        <div className="text-[11.5px] text-[var(--fg-3)]">
                          Compartida el{" "}
                          {new Date(share.shared_at).toLocaleDateString("es-ES", {
                            year: "numeric",
                            month: "short",
                            day: "numeric",
                          })}
                        </div>
                      )}
                    </div>
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      className="shrink-0 text-[var(--destructive)] hover:bg-[#ffdad6]/50 hover:text-[var(--destructive)]"
                      onClick={() => handleRevoke(share.user_id)}
                      disabled={unshareTemplate.isPending}
                      title="Revocar acceso"
                    >
                      <Trash2 className="size-3.5" />
                    </Button>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
