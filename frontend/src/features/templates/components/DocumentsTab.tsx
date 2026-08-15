import { Fragment, useState } from "react";
import {
  Trash2,
  FileText,
  FileSpreadsheet,
  FileArchive,
  ChevronDown,
  CornerDownRight,
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { useAuth } from "@/shared/lib/auth";
import {
  buildGroupDownloadUrl,
  triggerBlobDownload,
  useDocumentGroups,
} from "@/features/documents/api/queries";
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

/**
 * Combined-ZIP download for a document group (primary + related documents).
 *
 * Mirrors {@link DownloadButton}'s role rule: a non-admin gets a single
 * PDF-only package button (the backend 403s on `docx`), while an admin gets a
 * dropdown to choose the PDF or Word package. Downloads go through the shared
 * api client so the Authorization header is applied — never a bare `<a href>`.
 */
function GroupZipDownload({
  groupId,
  templateName,
}: {
  groupId: string;
  templateName: string;
}) {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const [downloadingFormat, setDownloadingFormat] = useState<
    "pdf" | "docx" | null
  >(null);
  const isDownloading = downloadingFormat !== null;

  async function handleZipDownload(format: "pdf" | "docx") {
    setDownloadingFormat(format);
    try {
      const url = buildGroupDownloadUrl(groupId, format);
      // Fixed save-as name for the whole package, regardless of format.
      const filename = `${templateName}_paquete.zip`;
      await triggerBlobDownload(url, filename);
    } catch {
      toast.error("Error al descargar el paquete");
    } finally {
      setDownloadingFormat(null);
    }
  }

  const outlineClass =
    "border-[rgba(195,198,215,0.40)] text-[var(--fg-2)] hover:bg-[var(--bg-accent)]/60 hover:text-[var(--primary)]";

  if (!isAdmin) {
    // Non-admin: single PDF-only package button — no Word option in the DOM.
    return (
      <Button
        variant="outline"
        size="sm"
        onClick={() => handleZipDownload("pdf")}
        disabled={isDownloading}
        className={outlineClass}
      >
        <FileArchive className="size-4" />
        {downloadingFormat === "pdf"
          ? "Descargando..."
          : "Descargar todo (ZIP)"}
      </Button>
    );
  }

  // Admin: choose PDF or Word package.
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        disabled={isDownloading}
        className={cn(
          buttonVariants({ variant: "outline", size: "sm" }),
          "gap-1",
          outlineClass,
        )}
      >
        <FileArchive className="size-4" />
        <span>
          {isDownloading ? "Descargando..." : "Descargar todo (ZIP)"}
        </span>
        <ChevronDown className="size-3.5 opacity-70" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem
          disabled={isDownloading}
          onClick={() => handleZipDownload("pdf")}
        >
          <FileArchive className="size-4" />
          Paquete PDF
        </DropdownMenuItem>
        <DropdownMenuItem
          disabled={isDownloading}
          onClick={() => handleZipDownload("docx")}
        >
          <FileArchive className="size-4" />
          Paquete Word (.docx)
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function DocumentsTab({ templateId }: DocumentsTabProps) {
  const [page, setPage] = useState(1);
  const size = 20;
  const { data, isLoading, isError, error } = useDocumentGroups({
    page,
    size,
    template_id: templateId,
  });
  const deleteDocument = useDeleteDocument();
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  // Expanded groups keyed by primary document id (always unique).
  const [expandedIds, setExpandedIds] = useState<Set<string>>(
    () => new Set(),
  );

  const toggleExpanded = (id: string) =>
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

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
          Historial de descargas y generaciones a partir de esta plantilla.
        </p>
      </div>

      {isLoading ? (
        <div className="space-y-2 p-5">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      ) : isError ? (
        <div className="m-5 rounded-[10px] bg-[#ffdad6] px-3.5 py-3 text-[13px] leading-[1.45] text-[#93000a]">
          Error al cargar documentos: {error?.message ?? "Error desconocido"}
        </div>
      ) : !data?.items.length ? (
        <div className="flex flex-col items-center justify-center p-12 text-center">
          <p className="text-[var(--fg-2)]">
            No se han generado documentos para esta plantilla.
          </p>
          <p className="mt-1 text-sm text-[var(--fg-3)]">
            Genere el primer documento desde «Generar Documento» arriba.
          </p>
        </div>
      ) : (
        <>
          {/* Wide table scrolls inside its own container — the page body
              must never scroll horizontally (STYLE_GUIDE.md §Responsive). */}
          <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-sm">
            <thead>
              <tr className="border-b border-[rgba(195,198,215,0.20)] bg-[var(--bg-page)]">
                <th className="px-5 py-2.5 text-left text-[11px] font-semibold uppercase tracking-[0.04em] text-[var(--fg-3)]">
                  Archivo
                </th>
                <th className="px-3 py-2.5 text-left text-[11px] font-semibold uppercase tracking-[0.04em] text-[var(--fg-3)]">
                  Tipo
                </th>
                <th className="px-3 py-2.5 text-left text-[11px] font-semibold uppercase tracking-[0.04em] text-[var(--fg-3)]">
                  Versión
                </th>
                <th className="px-3 py-2.5 text-left text-[11px] font-semibold uppercase tracking-[0.04em] text-[var(--fg-3)]">
                  Fecha
                </th>
                <th className="w-[300px] px-3 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {data.items.map((group) => {
                const { primary, related } = group;
                const hasRelated = related.length > 0;
                const isExpanded = expandedIds.has(primary.id);
                const isBulk = primary.generation_type === "bulk";
                const isConfirming = confirmDeleteId === primary.id;
                return (
                  <Fragment key={primary.id}>
                    <tr className="border-b border-[rgba(195,198,215,0.15)] transition-colors hover:bg-[var(--bg-page)]">
                      <td className="px-5 py-3">
                        <div className="flex items-start gap-2.5">
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
                          <div className="min-w-0">
                            <span className="block max-w-[260px] truncate font-medium text-[var(--fg-1)]">
                              {primary.docx_file_name}
                            </span>
                            {hasRelated && (
                              <button
                                type="button"
                                onClick={() => toggleExpanded(primary.id)}
                                aria-expanded={isExpanded}
                                className="mt-1 inline-flex items-center gap-1 rounded-md text-[12px] font-medium text-[var(--primary)] transition-colors hover:text-[#004ac6] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
                              >
                                <ChevronDown
                                  className={cn(
                                    "size-3.5 transition-transform",
                                    isExpanded && "rotate-180",
                                  )}
                                />
                                +{related.length}{" "}
                                {related.length === 1
                                  ? "documento relacionado"
                                  : "documentos relacionados"}
                              </button>
                            )}
                          </div>
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
                        <Badge
                          variant="outline"
                          className="rounded-full border-[rgba(195,198,215,0.40)] text-[var(--fg-3)]"
                        >
                          v{primary.template_version}
                        </Badge>
                      </td>
                      <td className="px-3 py-3 text-[var(--fg-3)]">
                        {formatDate(primary.created_at)}
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex flex-wrap items-center justify-end gap-1.5">
                          {hasRelated && group.group_id && (
                            <GroupZipDownload
                              groupId={group.group_id}
                              templateName={primary.template_name}
                            />
                          )}
                          <DownloadButton
                            documentId={primary.id}
                            baseFileName={primary.docx_file_name}
                            via="direct"
                          />
                          {isConfirming ? (
                            <>
                              <Button
                                size="sm"
                                disabled={deleteDocument.isPending}
                                onClick={() => handleDelete(primary.id)}
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
                              onClick={() => setConfirmDeleteId(primary.id)}
                              className="text-[var(--destructive)] hover:bg-[#ffdad6]/50 hover:text-[var(--destructive)]"
                            >
                              <Trash2 className="size-3.5" />
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>

                    {hasRelated &&
                      isExpanded &&
                      related.map((rel) => (
                        <tr
                          key={rel.id}
                          className="border-b border-[rgba(195,198,215,0.15)] bg-[var(--bg-page)]/60"
                        >
                          <td className="px-5 py-2.5">
                            <div className="flex items-center gap-2 pl-8">
                              <CornerDownRight className="size-3.5 shrink-0 text-[var(--fg-3)]" />
                              <span className="max-w-[240px] truncate font-medium text-[var(--fg-2)]">
                                {rel.related_label ?? rel.docx_file_name}
                              </span>
                            </div>
                          </td>
                          <td className="px-3 py-2.5">
                            <Badge
                              variant="outline"
                              className="rounded-full border-[rgba(195,198,215,0.40)] text-[var(--fg-3)]"
                            >
                              Relacionado
                            </Badge>
                          </td>
                          <td className="px-3 py-2.5">
                            <Badge
                              variant="outline"
                              className="rounded-full border-[rgba(195,198,215,0.40)] text-[var(--fg-3)]"
                            >
                              v{rel.template_version}
                            </Badge>
                          </td>
                          <td className="px-3 py-2.5 text-[var(--fg-3)]">
                            {formatDate(rel.created_at)}
                          </td>
                          <td className="px-3 py-2.5">
                            <div className="flex items-center justify-end gap-1.5">
                              <DownloadButton
                                documentId={rel.id}
                                baseFileName={rel.docx_file_name}
                                via="direct"
                              />
                            </div>
                          </td>
                        </tr>
                      ))}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
          </div>

          {totalPages > 1 && (
            <div className="flex flex-wrap items-center justify-between gap-2 border-t border-[rgba(195,198,215,0.20)] px-5 py-3">
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
