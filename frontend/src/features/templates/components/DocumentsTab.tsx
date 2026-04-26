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
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useDocuments } from "@/features/documents/api/queries";
import { useDeleteDocument } from "@/features/documents/api/mutations";
import { DownloadButton } from "@/features/documents/components/DownloadButton";

interface DocumentsTabProps {
  templateId: string;
}

function formatDate(dateString: string) {
  return new Date(dateString).toLocaleDateString("es-ES", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function DocumentsTab({ templateId }: DocumentsTabProps) {
  const [page, setPage] = useState(1);
  const size = 20;
  const { data, isLoading, isError, error } = useDocuments({
    page,
    size,
    template_id: templateId,
  });
  const deleteDocument = useDeleteDocument();
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  const handleDelete = async (documentId: string) => {
    try {
      await deleteDocument.mutateAsync(documentId);
      toast.success("Documento eliminado correctamente");
    } catch {
      toast.error("Error al eliminar el documento");
    } finally {
      setConfirmDeleteId(null);
    }
  };

  const totalPages = data ? Math.ceil(data.total / size) : 0;

  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <div className="rounded-lg border border-destructive/50 bg-destructive/5 p-4 text-sm text-destructive">
        Error al cargar documentos: {error?.message ?? "Error desconocido"}
      </div>
    );
  }

  if (!data?.items.length) {
    return (
      <div className="flex flex-col items-center justify-center rounded-lg border border-dashed p-12 text-center">
        <p className="text-muted-foreground">
          No se han generado documentos para esta plantilla.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Nombre archivo</TableHead>
            <TableHead>Tipo</TableHead>
            <TableHead>Fecha</TableHead>
            <TableHead className="w-[220px]">Acciones</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.items.map((doc) => (
            <TableRow key={doc.id}>
              <TableCell className="max-w-[250px] truncate font-medium">
                {doc.file_name}
              </TableCell>
              <TableCell>
                <Badge
                  variant={
                    doc.generation_type === "bulk" ? "default" : "secondary"
                  }
                >
                  {doc.generation_type === "bulk" ? "Masivo" : "Individual"}
                </Badge>
              </TableCell>
              <TableCell className="text-muted-foreground">
                {formatDate(doc.created_at)}
              </TableCell>
              <TableCell>
                <div className="flex items-center gap-1">
                  <DownloadButton
                    documentId={doc.id}
                    baseFileName={doc.file_name}
                    via="direct"
                  />
                  {confirmDeleteId === doc.id ? (
                    <div className="flex items-center gap-1">
                      <Button
                        variant="destructive"
                        size="sm"
                        disabled={deleteDocument.isPending}
                        onClick={() => handleDelete(doc.id)}
                      >
                        {deleteDocument.isPending ? "..." : "Confirmar"}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setConfirmDeleteId(null)}
                      >
                        No
                      </Button>
                    </div>
                  ) : (
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      title="Eliminar"
                      onClick={() => setConfirmDeleteId(doc.id)}
                    >
                      <Trash2Icon className="size-4 text-destructive" />
                    </Button>
                  )}
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Mostrando {data.items.length} de {data.total} documentos
          </p>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              Anterior
            </Button>
            <span className="text-sm text-muted-foreground">
              Pagina {page} de {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
            >
              Siguiente
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
