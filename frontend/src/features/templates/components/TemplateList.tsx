import { useState, useEffect } from "react";
import { useNavigate } from "@tanstack/react-router";
import { Search, FileText, Folder, Share2, Code } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useTemplates, type Template } from "../api";

export function TemplateList() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  const { data, isLoading, isError, error } = useTemplates({
    search: debouncedSearch || undefined,
  });

  const items = data?.items ?? [];
  const total = data?.total ?? items.length;
  const sharedCount = items.filter((t) => t.access_type === "shared").length;
  const variablesTotal = items.reduce((sum, t) => sum + t.variables.length, 0);

  return (
    <div className="space-y-5">
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

      {/* Search row */}
      <div className="flex items-center justify-between gap-3">
        <div className="relative w-full max-w-sm">
          <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-[var(--fg-3)]" />
          <Input
            placeholder="Buscar plantillas..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        {!isLoading && !isError && (
          <div className="text-xs text-[var(--fg-3)]">
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
        <div className="rounded-lg border border-destructive/50 bg-destructive/5 p-4 text-sm text-destructive">
          Error al cargar plantillas: {error?.message ?? "Error desconocido"}
        </div>
      ) : !items.length ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-[rgba(195,198,215,0.4)] bg-white/50 p-12 text-center">
          <p className="text-[var(--fg-2)]">
            {debouncedSearch
              ? "No se encontraron plantillas que coincidan con su búsqueda."
              : "Aún no hay plantillas. Suba su primera plantilla para comenzar."}
          </p>
        </div>
      ) : (
        <div className="grid gap-3.5 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((template) => (
            <TemplateCard
              key={template.id}
              template={template}
              onOpen={() =>
                navigate({
                  to: "/templates/$templateId",
                  params: { templateId: template.id },
                })
              }
            />
          ))}
        </div>
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
  onOpen,
}: {
  template: Template;
  onOpen: () => void;
}) {
  const formattedDate = new Date(template.updated_at ?? template.created_at).toLocaleDateString("es-ES", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

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
        </div>
      </div>

      <div className="space-y-1">
        <h3 className="text-sm font-semibold leading-tight text-[var(--fg-1)] group-hover/card:text-[var(--primary)]">
          {template.name}
        </h3>
        <p className="line-clamp-2 min-h-[34px] text-xs leading-[1.5] text-[var(--fg-3)]">
          {template.description || "Sin descripción"}
        </p>
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
