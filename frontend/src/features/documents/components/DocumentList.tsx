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
import { useDocuments } from "../api/queries";
import { useDeleteDocument } from "../api/mutations";
import { DownloadButton } from "./DownloadButton";

export function DocumentList() {
  const [page, setPage] = useState(1);
  const size = 20;
  const { data, isLoading, isError, error } = useDocuments({ page, size });
  const deleteDocument = useDeleteDocument();
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  function formatDate(dateString: string) {
    return new Date(dateString).toLocaleDateString("es-ES", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

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

  return (
    <div className="space-y-4">
      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      ) : isError ? (
        <div className="rounded-lg border border-destructive/50 bg-destructive/5 p-4 text-sm text-destructive">
          Error al cargar documentos: {error?.message ?? "Error desconocido"}
        </div>
      ) : !data?.items.length ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed p-12 text-center">
          <p className="text-muted-foreground">
            No hay documentos generados aun. Genere documentos desde una
            plantilla para verlos aqui.
          </p>
        </div>
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Nombre archivo</TableHead>
                <TableHead>Tipo</TableHead>
                <TableHead>Variables</TableHead>
                <TableHead>Estado</TableHead>
                <TableHead>Fecha</TableHead>
                <TableHead className="w-[120px]">Acciones</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.items.map((doc) => {
                const variableCount = Object.keys(
                  doc.variables_snapshot || {},
                ).length;
                const variableEntries = Object.entries(
                  doc.variables_snapshot || {},
                );
                const variableSummary = variableEntries
                  .slice(0, 3)
                  .map(([k, v]) => `${k}: ${v}`)
                  .join(", ");
                const hasMore = variableEntries.length > 3;

                return (
                  <TableRow key={doc.id}>
                    <TableCell className="font-medium max-w-[250px] truncate">
                      {doc.file_name}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          doc.generation_type === "bulk"
                            ? "default"
                            : "secondary"
                        }
                      >
                        {doc.generation_type === "bulk"
                          ? "Masivo"
                          : "Individual"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <span
                        className="text-sm text-muted-foreground cursor-default"
                        title={variableSummary + (hasMore ? "..." : "")}
                      >
                        {variableCount} variable
                        {variableCount !== 1 ? "s" : ""}
                      </span>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          doc.status === "completed"
                            ? "secondary"
                            : "destructive"
                        }
                      >
                        {doc.status === "completed" ? "Completado" : doc.status}
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
                              {deleteDocument.isPending
                                ? "..."
                                : "Confirmar"}
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
                );
              })}
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
        </>
      )}
    </div>
  );
}
