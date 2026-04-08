import { useState } from "react";
import { toast } from "sonner";
import { Share2Icon, Trash2Icon, UserPlusIcon } from "lucide-react";

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
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

import { useTemplateShares } from "../api/queries";
import { useShareTemplate, useUnshareTemplate } from "../api/mutations";

interface ShareTemplateDialogProps {
  templateId: string;
  templateName: string;
}

export function ShareTemplateDialog({
  templateId,
  templateName,
}: ShareTemplateDialogProps) {
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");

  const { data: shares, isLoading: sharesLoading } =
    useTemplateShares(templateId);

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
            err &&
            typeof err === "object" &&
            "response" in err
              ? (err as { response?: { status?: number; data?: { detail?: string } } }).response
                  ?.status
              : undefined;

          const detail =
            err &&
            typeof err === "object" &&
            "response" in err
              ? (err as { response?: { data?: { detail?: string } } }).response
                  ?.data?.detail
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
            (err as { response?: { data?: { detail?: string } } }).response
              ?.data?.detail;
          toast.error((detail as string) || "Error al revocar el acceso");
        },
      }
    );
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button
            variant="outline"
            className="border-[rgba(195,198,215,0.3)] hover:bg-[#dbe1ff]/50 hover:text-[#004ac6] transition-all"
          />
        }
      >
        <Share2Icon className="size-4" />
        Compartir
      </DialogTrigger>

      <DialogContent className="sm:max-w-lg bg-white/80 backdrop-blur-xl border-0 shadow-[0_12px_32px_rgba(25,28,30,0.1)]">
        <DialogHeader>
          <DialogTitle>Compartir Plantilla</DialogTitle>
          <DialogDescription>
            Comparta "{templateName}" con otros usuarios de su organización.
          </DialogDescription>
        </DialogHeader>

        {/* Add new share by email */}
        <div className="space-y-2">
          <Label>Agregar usuario por correo</Label>
          <div className="flex gap-2">
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleShare();
              }}
              placeholder="correo@ejemplo.com"
              className="flex-1 bg-[#e6e8ea] border-transparent focus:border-[#2563eb] focus:ring-[#2563eb]/20"
            />
            <Button
              onClick={handleShare}
              disabled={!email.trim() || shareTemplate.isPending}
              className="bg-gradient-to-br from-[#004ac6] to-[#2563eb] text-white shadow-[0_4px_12px_rgba(0,74,198,0.3)] shrink-0"
            >
              <UserPlusIcon className="size-4" />
              {shareTemplate.isPending ? "Compartiendo..." : "Compartir"}
            </Button>
          </div>
        </div>

        {/* Current shares list */}
        <div className="space-y-2">
          <Label>Usuarios con acceso</Label>
          {sharesLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 2 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : !shares || shares.length === 0 ? (
            <div className="rounded-lg border border-dashed border-[rgba(195,198,215,0.3)] p-4 text-center">
              <p className="text-sm text-[#434655]">
                Esta plantilla aún no ha sido compartida con nadie.
              </p>
            </div>
          ) : (
            <div className="space-y-2 max-h-52 overflow-y-auto">
              {shares.map((share) => (
                <div
                  key={share.id}
                  className="flex items-center justify-between rounded-lg border border-[rgba(195,198,215,0.2)] bg-[#f7f9fb] px-3 py-2"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-[#191c1e]">
                      {share.user_email ?? share.user_id}
                    </p>
                    {share.shared_at && (
                      <p className="text-xs text-[#434655]">
                        Compartido el{" "}
                        {new Date(share.shared_at).toLocaleDateString("es-ES", {
                          year: "numeric",
                          month: "short",
                          day: "numeric",
                        })}
                      </p>
                    )}
                  </div>
                  <div className="ml-2 flex items-center gap-2">
                    <Badge className="bg-[#dbe1ff] text-[#004ac6] border-0 rounded-full text-xs">
                      Compartido
                    </Badge>
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      className="text-[#ba1a1a] hover:bg-[#ffdad6]/50 hover:text-[#93000a] shrink-0"
                      onClick={() => handleRevoke(share.user_id)}
                      disabled={unshareTemplate.isPending}
                      title="Revocar acceso"
                    >
                      <Trash2Icon className="size-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
