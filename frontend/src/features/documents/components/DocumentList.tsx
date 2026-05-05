import { useState } from "react";
import { FileSpreadsheet, FileText, Trash2 } from "lucide-react";
import { toast } from "sonner";
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
    <div className="overflow-hidden rounded-xl bg-white shadow-[var(--shadow-md)]">
      <div className="border-b border-[rgba(195,198,215,0.20)] px-5 py-4">
        <h3 className="m-0 text-base font-bold tracking-tight text-[var(--fg-1)]">
          Documentos generados
        </h3>
        <p className="mt-0.5 text-[12.5px] text-[var(--fg-3)]">
          Historial completo de documentos creados desde sus plantillas.
        </p>
      </div>

      {isLoading ? (
        <div className="space-y-2 p-5">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      ) : isError ? (
        <div className="m-5 rounded-lg border border-destructive/50 bg-destructive/5 p-4 text-sm text-destructive">
          Error al cargar documentos: {error?.message ?? "Error desconocido"}
        </div>
      ) : !data?.items.length ? (
        <div className="flex flex-col items-center justify-center p-12 text-center">
          <p className="text-[var(--fg-2)]">
            No hay documentos generados aún. Genere documentos desde una
            plantilla para verlos aquí.
          </p>
        </div>
      ) : (
        <>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[rgba(195,198,215,0.20)] bg-[var(--bg-page)]">
                <th className="px-5 py-2.5 text-left text-[11px] font-semibold uppercase tracking-[0.04em] text-[var(--fg-3)]">
                  Archivo
                </th>
                <th className="px-3 py-2.5 text-left text-[11px] font-semibold uppercase tracking-[0.04em] text-[var(--fg-3)]">
                  Tipo
                </th>
                <th className="px-3 py-2.5 text-left text-[11px] font-semibold uppercase tracking-[0.04em] text-[var(--fg-3)]">
                  Variables
                </th>
                <th className="px-3 py-2.5 text-left text-[11px] font-semibold uppercase tracking-[0.04em] text-[var(--fg-3)]">
                  Estado
                </th>
                <th className="px-3 py-2.5 text-left text-[11px] font-semibold uppercase tracking-[0.04em] text-[var(--fg-3)]">
                  Fecha
                </th>
                <th className="w-[220px] px-3 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {data.items.map((doc) => {
                const isBulk = doc.generation_type === "bulk";
                const isConfirming = confirmDeleteId === doc.id;
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
                const isCompleted = doc.status === "completed";

                return (
                  <tr
                    key={doc.id}
                    className="border-b border-[rgba(195,198,215,0.15)] transition-colors last:border-b-0 hover:bg-[var(--bg-page)]"
                  >
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-2.5">
                        <span
                          className={`inline-flex size-8 shrink-0 items-center justify-center rounded-lg ${
                            isBulk
                              ? "bg-[#d1fae5] text-[#065f46]"
                              : "bg-[var(--bg-accent)] text-[var(--primary)]"
                          }`}
                        >
                          {isBulk ? (
                            <FileSpreadsheet className="size-4" />
                          ) : (
                            <FileText className="size-4" />
                          )}
                        </span>
                        <span className="max-w-[260px] truncate font-medium text-[var(--fg-1)]">
                          {doc.docx_file_name}
                        </span>
                      </div>
                    </td>
                    <td className="px-3 py-3">
                      <Badge
                        className={
                          isBulk
                            ? "rounded-full border-0 bg-[#d1fae5] font-semibold text-[#065f46] hover:bg-[#d1fae5]"
                            : "rounded-full border-0 bg-[var(--bg-accent)] font-semibold text-[var(--primary)] hover:bg-[var(--bg-accent)]"
                        }
                      >
                        {isBulk ? "Masivo" : "Individual"}
                      </Badge>
                    </td>
                    <td className="px-3 py-3">
                      <span
                        className="cursor-default text-[13px] text-[var(--fg-3)]"
                        title={variableSummary + (hasMore ? "..." : "")}
                      >
                        {variableCount} variable
                        {variableCount !== 1 ? "s" : ""}
                      </span>
                    </td>
                    <td className="px-3 py-3">
                      <Badge
                        className={
                          isCompleted
                            ? "rounded-full border-0 bg-[#d1fae5] font-semibold text-[#065f46] hover:bg-[#d1fae5]"
                            : "rounded-full border-0 bg-[#ffdad6] font-semibold text-[#93000a] hover:bg-[#ffdad6]"
                        }
                      >
                        {isCompleted ? "Completado" : doc.status}
                      </Badge>
                    </td>
                    <td className="px-3 py-3 text-[var(--fg-3)]">
                      {formatDate(doc.created_at)}
                    </td>
                    <td className="px-3 py-3">
                      <div className="flex items-center justify-end gap-1.5">
                        <DownloadButton
                          documentId={doc.id}
                          baseFileName={doc.docx_file_name}
                          via="direct"
                        />
                        {isConfirming ? (
                          <>
                            <Button
                              size="sm"
                              disabled={deleteDocument.isPending}
                              onClick={() => handleDelete(doc.id)}
                              className="bg-[var(--destructive)] font-semibold text-white hover:bg-[#93000a]"
                            >
                              {deleteDocument.isPending ? "…" : "Confirmar"}
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => setConfirmDeleteId(null)}
                            >
                              No
                            </Button>
                          </>
                        ) : (
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            title="Eliminar"
                            onClick={() => setConfirmDeleteId(doc.id)}
                            className="text-[var(--destructive)] hover:bg-[#ffdad6]/50 hover:text-[var(--destructive)]"
                          >
                            <Trash2 className="size-3.5" />
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {totalPages > 1 && (
            <div className="flex items-center justify-between border-t border-[rgba(195,198,215,0.20)] px-5 py-3">
              <p className="text-xs text-[var(--fg-3)]">
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
                <span className="text-xs text-[var(--fg-3)]">
                  Página {page} de {totalPages}
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
