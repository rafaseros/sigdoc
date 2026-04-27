import { useState } from "react";
import { Trash2Icon } from "lucide-react";
import { toast } from "sonner";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
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

export function SharesTab({ templateId, templateName }: SharesTabProps) {
  const { data: shares, isLoading, isError, error } = useTemplateShares(templateId);
  const unshareTemplate = useUnshareTemplate();
  const [confirmRevokeId, setConfirmRevokeId] = useState<string | null>(null);

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

  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <div className="rounded-lg border border-destructive/50 bg-destructive/5 p-4 text-sm text-destructive">
        Error al cargar compartidos: {error?.message ?? "Error desconocido"}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header action */}
      <div className="flex justify-end">
        <ShareTemplateDialog templateId={templateId} templateName={templateName} />
      </div>

      {!shares || shares.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed p-12 text-center">
          <p className="text-muted-foreground">
            Esta plantilla no se ha compartido con nadie.
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            Usá el botón "+ Compartir" para agregar usuarios.
          </p>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Email</TableHead>
              <TableHead>Compartido el</TableHead>
              <TableHead className="w-[160px]">Acciones</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {shares.map((share) => (
              <TableRow key={share.id}>
                <TableCell className="font-medium">
                  {share.user_email ?? share.user_id}
                </TableCell>
                <TableCell className="text-muted-foreground">
                  {share.shared_at ? formatDate(share.shared_at) : "—"}
                </TableCell>
                <TableCell>
                  {confirmRevokeId === share.user_id ? (
                    <div className="flex items-center gap-1">
                      <Button
                        variant="destructive"
                        size="sm"
                        disabled={unshareTemplate.isPending}
                        onClick={() => handleRevoke(share.user_id)}
                      >
                        {unshareTemplate.isPending ? "..." : "Confirmar"}
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
                      className="text-[#ba1a1a] hover:bg-[#ffdad6]/50 hover:text-[#93000a]"
                      onClick={() => setConfirmRevokeId(share.user_id)}
                      title="Revocar acceso"
                    >
                      <Trash2Icon className="size-4" />
                      Revocar
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
