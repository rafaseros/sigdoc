import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import {
  Search,
  FileText,
  Folder,
  FolderInput,
  Share2,
  Code,
  LayoutGrid,
  List as ListIcon,
  Eye,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useTemplates, useFolders, type Template } from "../api";
import { FolderSidebar, type FolderFilter } from "./FolderSidebar";
import { MoveToFolderDialog } from "./MoveToFolderDialog";

type ViewMode = "cards" | "table";

const VIEW_MODE_STORAGE_KEY = "templates:view-mode";
const PAGE_SIZE = 20;

function readStoredViewMode(): ViewMode {
  if (typeof window === "undefined") return "cards";
  try {
    return window.localStorage.getItem(VIEW_MODE_STORAGE_KEY) === "table"
      ? "table"
      : "cards";
  } catch {
    // localStorage unavailable (private browsing, disabled storage, etc.) —
    // fall back to the default view mode for this session only.
    return "cards";
  }
}

function formatDate(dateString: string) {
  return new Date(dateString).toLocaleDateString("es-ES", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function TemplateList() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [page, setPage] = useState(1);
  const [viewMode, setViewMode] = useState<ViewMode>(readStoredViewMode);
  const [activeFolder, setActiveFolder] = useState<FolderFilter>(undefined);
  const [movingTemplate, setMovingTemplate] = useState<Template | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  // A new search invalidates the current page — always land back on page 1.
  useEffect(() => {
    setPage(1);
  }, [debouncedSearch]);

  // Switching folders is the same kind of filter change as search — the
  // previous page number no longer means anything for the new filter.
  useEffect(() => {
    setPage(1);
  }, [activeFolder]);

  useEffect(() => {
    try {
      window.localStorage.setItem(VIEW_MODE_STORAGE_KEY, viewMode);
    } catch {
      // localStorage unavailable — view mode still works in-memory for this
      // session, it just won't persist across reloads.
    }
  }, [viewMode]);

  const { data, isLoading, isError, error } = useTemplates({
    search: debouncedSearch || undefined,
    page,
    size: PAGE_SIZE,
    folder_id: activeFolder,
  });
  const { data: folders } = useFolders();

  const folderNameById = useMemo(
    () => new Map((folders ?? []).map((f) => [f.id, f.name])),
    [folders],
  );

  const items = data?.items ?? [];
  const total = data?.total ?? items.length;
  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;
  const sharedCount = items.filter((t) => t.access_type === "shared").length;
  const variablesTotal = items.reduce((sum, t) => sum + t.variables.length, 0);

  // If the total shrinks while we're on a page that no longer exists (e.g.
  // a delete or cache invalidation drops the count below the current page),
  // clamp back to the last valid page instead of stranding the user on an
  // empty page.
  useEffect(() => {
    if (data && totalPages >= 1 && page > totalPages) {
      setPage(totalPages);
    }
  }, [data, page, totalPages]);

  function goToDetail(templateId: string) {
    navigate({
      to: "/templates/$templateId",
      params: { templateId },
    });
  }

  return (
    <div className="grid gap-5 lg:grid-cols-[240px_1fr]">
      <FolderSidebar
        activeFolder={activeFolder}
        onSelectFolder={setActiveFolder}
        totalCount={activeFolder === undefined ? data?.total : undefined}
      />

      <div className="min-w-0 space-y-5">
      {/* Stat cards */}
      <div className="grid gap-3 sm:grid-cols-3">
        <StatCard
          label="Plantillas"
          value={total}
          hint="visibles para tu rol"
          icon={<Folder className="size-4" />}
        />
        <StatCard
          label="Compartidas"
          value={sharedCount}
          hint="con miembros del equipo"
          icon={<Share2 className="size-4" />}
        />
        <StatCard
          label="Variables totales"
          value={variablesTotal}
          hint="a lo largo de plantillas"
          icon={<Code className="size-4" />}
        />
      </div>

      {/* Search row + view toggle */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex flex-1 items-center gap-2">
          <div className="relative w-full max-w-sm">
            <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-[var(--fg-3)]" />
            <Input
              placeholder="Buscar plantillas..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>
          <div className="inline-flex items-center gap-0.5 rounded-lg bg-[var(--bg-muted)] p-0.5">
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              aria-label="Vista de tarjetas"
              title="Vista de tarjetas"
              aria-pressed={viewMode === "cards"}
              onClick={() => setViewMode("cards")}
              className={
                viewMode === "cards"
                  ? "bg-white text-[var(--primary)] shadow-[var(--shadow-sm)] hover:bg-white"
                  : "text-[var(--fg-3)]"
              }
            >
              <LayoutGrid className="size-4" />
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              aria-label="Vista de tabla"
              title="Vista de tabla"
              aria-pressed={viewMode === "table"}
              onClick={() => setViewMode("table")}
              className={
                viewMode === "table"
                  ? "bg-white text-[var(--primary)] shadow-[var(--shadow-sm)] hover:bg-white"
                  : "text-[var(--fg-3)]"
              }
            >
              <ListIcon className="size-4" />
            </Button>
          </div>
        </div>
        {!isLoading && !isError && (
          <div className="shrink-0 text-xs text-[var(--fg-3)]">
            {items.length} de {total} {total === 1 ? "plantilla" : "plantillas"}
          </div>
        )}
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="grid gap-3.5 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-[160px] w-full rounded-xl" />
          ))}
        </div>
      ) : isError ? (
        <div className="rounded-[10px] bg-[#ffdad6] px-3.5 py-3 text-[13px] leading-[1.45] text-[#93000a]">
          Error al cargar plantillas: {error?.message ?? "Error desconocido"}
        </div>
      ) : !items.length ? (
        debouncedSearch || activeFolder !== undefined ? (
          <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-[rgba(195,198,215,0.4)] bg-white/50 p-12 text-center">
            <p className="text-[var(--fg-2)]">
              {debouncedSearch
                ? "No se encontraron plantillas que coincidan con su búsqueda."
                : "No hay plantillas en esta carpeta."}
            </p>
          </div>
        ) : (
          <Card className="border-0 bg-white shadow-[var(--shadow-md)]">
            <CardContent className="pt-6 text-center">
              <p className="text-[var(--fg-2)]">Aún no hay plantillas.</p>
              <p className="mt-1 text-sm text-[var(--fg-3)]">
                Use el botón <strong>Subir Plantilla</strong> para comenzar.
              </p>
            </CardContent>
          </Card>
        )
      ) : viewMode === "table" ? (
        <div className="overflow-hidden rounded-xl bg-white shadow-[var(--shadow-sm)] ring-1 ring-[rgba(195,198,215,0.30)]">
          <Table>
            <TableHeader>
              <TableRow className="border-b border-[rgba(195,198,215,0.2)] bg-[var(--bg-muted)] hover:bg-[var(--bg-muted)]">
                <TableHead className="font-semibold text-[var(--fg-1)]">
                  Nombre
                </TableHead>
                <TableHead className="font-semibold text-[var(--fg-1)]">
                  Propietario
                </TableHead>
                <TableHead className="font-semibold text-[var(--fg-1)]">
                  Versión
                </TableHead>
                <TableHead className="font-semibold text-[var(--fg-1)]">
                  Variables
                </TableHead>
                <TableHead className="font-semibold text-[var(--fg-1)]">
                  Actualizada
                </TableHead>
                <TableHead className="w-[80px] text-right font-semibold text-[var(--fg-1)]">
                  Acciones
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((template) => (
                <TableRow
                  key={template.id}
                  className="border-b border-[rgba(195,198,215,0.1)] transition-colors hover:bg-[var(--bg-page)]"
                >
                  <TableCell className="py-3">
                    <button
                      type="button"
                      onClick={() => goToDetail(template.id)}
                      className="text-left text-sm font-semibold text-[var(--fg-1)] hover:text-[var(--primary)] hover:underline"
                    >
                      {template.name}
                    </button>
                  </TableCell>
                  <TableCell className="text-sm text-[var(--fg-3)]">
                    {template.owner_name ?? template.shared_by_email ?? "—"}
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant="outline"
                      className="rounded-full border-[rgba(37,99,235,0.30)] text-[var(--primary)]"
                    >
                      v{template.current_version}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-sm text-[var(--fg-3)]">
                    {template.variables.length}
                  </TableCell>
                  <TableCell className="text-sm text-[var(--fg-3)]">
                    {formatDate(template.updated_at ?? template.created_at)}
                  </TableCell>
                  <TableCell>
                    <div className="flex justify-end">
                      {template.is_owner && (
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          title="Mover a carpeta"
                          onClick={() => setMovingTemplate(template)}
                          className="text-[var(--fg-2)] hover:bg-[var(--bg-accent)]/60 hover:text-[var(--primary)]"
                        >
                          <FolderInput className="size-4" />
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        title="Ver detalle"
                        onClick={() => goToDetail(template.id)}
                        className="text-[var(--fg-2)] hover:bg-[var(--bg-accent)]/60 hover:text-[var(--primary)]"
                      >
                        <Eye className="size-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : (
        <div className="grid gap-3.5 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((template) => (
            <TemplateCard
              key={template.id}
              template={template}
              folderName={
                template.folder_id
                  ? folderNameById.get(template.folder_id)
                  : undefined
              }
              onOpen={() => goToDetail(template.id)}
            />
          ))}
        </div>
      )}

      {/* Pager */}
      {data && data.total > PAGE_SIZE && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-white px-4 py-3 shadow-[var(--shadow-sm)] ring-1 ring-[rgba(195,198,215,0.30)]">
          <p className="text-xs text-[var(--fg-3)]">
            Mostrando {items.length} de {data.total} plantillas
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
            <span className="text-xs font-medium text-[var(--fg-2)]">
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
      </div>

      {movingTemplate && (
        <MoveToFolderDialog
          templateId={movingTemplate.id}
          templateName={movingTemplate.name}
          currentFolderId={movingTemplate.folder_id}
          open={!!movingTemplate}
          onOpenChange={(open) => {
            if (!open) setMovingTemplate(null);
          }}
        />
      )}
    </div>
  );
}

function StatCard({
  label,
  value,
  hint,
  icon,
}: {
  label: string;
  value: number;
  hint: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="relative overflow-hidden rounded-xl bg-white p-4 shadow-[var(--shadow-sm)] ring-1 ring-[rgba(195,198,215,0.30)]">
      <div className="text-xs font-medium uppercase tracking-[0.04em] text-[var(--fg-3)]">
        {label}
      </div>
      <div className="mt-1 text-3xl font-bold tracking-tight text-[var(--fg-1)]">
        {value}
      </div>
      <div className="mt-0.5 text-xs text-[var(--fg-3)]">{hint}</div>
      <div className="absolute right-3 top-3 inline-flex size-8 items-center justify-center rounded-lg bg-[var(--bg-accent)] text-[var(--primary)]">
        {icon}
      </div>
    </div>
  );
}

function TemplateCard({
  template,
  folderName,
  onOpen,
}: {
  template: Template;
  /** Resolved folder name for this template's `folder_id`. Omitted entirely
   * (no chip) when the template is unfiled or the folders list hasn't
   * loaded yet — never renders a raw uuid. */
  folderName?: string;
  onOpen: () => void;
}) {
  const formattedDate = formatDate(template.updated_at ?? template.created_at);
  const ownerLabel = template.owner_name ?? template.shared_by_email;

  return (
    <button
      type="button"
      onClick={onOpen}
      className="group/card flex flex-col gap-3 rounded-xl bg-white p-4 text-left shadow-[var(--shadow-sm)] ring-1 ring-[rgba(195,198,215,0.30)] transition-all duration-150 hover:-translate-y-0.5 hover:shadow-[var(--shadow-md)] hover:ring-[rgba(37,99,235,0.30)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="inline-flex size-10 items-center justify-center rounded-[10px] bg-[var(--bg-accent)] text-[var(--primary)]">
          <FileText className="size-5" />
        </div>
        <div className="flex flex-wrap justify-end gap-1.5">
          <Badge
            variant="outline"
            className="rounded-full border-[rgba(37,99,235,0.30)] text-[var(--primary)]"
          >
            v{template.current_version}
          </Badge>
          {template.access_type === "shared" && (
            <Badge className="rounded-full border-0 bg-[var(--bg-accent)] text-[var(--primary)] hover:bg-[var(--bg-accent)]">
              Compartida
            </Badge>
          )}
          {folderName && (
            <Badge
              variant="outline"
              className="rounded-full border-[rgba(195,198,215,0.40)] text-[var(--fg-3)]"
            >
              <Folder className="mr-1 size-3" />
              {folderName}
            </Badge>
          )}
        </div>
      </div>

      <div className="space-y-1">
        <h3 className="text-sm font-semibold leading-tight text-[var(--fg-1)] group-hover/card:text-[var(--primary)]">
          {template.name}
        </h3>
        <p className="line-clamp-2 min-h-[34px] text-xs leading-[1.5] text-[var(--fg-3)]">
          {template.description || "Sin descripción"}
        </p>
        {template.access_type === "shared" && ownerLabel && (
          <p className="text-[11px] text-[var(--fg-3)]">
            Compartida por{" "}
            <span className="font-medium text-[var(--primary)]">
              {ownerLabel}
            </span>
          </p>
        )}
      </div>

      <div className="flex items-center justify-between border-t border-[rgba(195,198,215,0.20)] pt-2.5 text-[11.5px] text-[var(--fg-3)]">
        <span className="inline-flex items-center gap-1">
          <Code className="size-3 text-[var(--primary)]" />
          {template.variables.length} {template.variables.length === 1 ? "variable" : "variables"}
        </span>
        <span>{formattedDate}</span>
      </div>
    </button>
  );
}
