import { useState, useEffect } from "react";
import { useNavigate } from "@tanstack/react-router";
import { SearchIcon, EyeIcon } from "lucide-react";
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
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useTemplates } from "../api";

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

  function formatDate(dateString: string) {
    return new Date(dateString).toLocaleDateString("es-ES", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  }

  function truncate(text: string | null, maxLength: number) {
    if (!text) return "-";
    return text.length > maxLength ? text.slice(0, maxLength) + "..." : text;
  }

  return (
    <div className="space-y-4">
      <div className="relative max-w-sm">
        <SearchIcon className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-[#434655]" />
        <Input
          placeholder="Buscar plantillas..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-9 bg-[#e6e8ea] border-transparent focus:border-[#2563eb] focus:ring-[#2563eb]/20 transition-all"
        />
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      ) : isError ? (
        <div className="rounded-lg border border-destructive/50 bg-destructive/5 p-4 text-sm text-destructive">
          Error al cargar plantillas: {error?.message ?? "Error desconocido"}
        </div>
      ) : !data?.items.length ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-[rgba(195,198,215,0.3)] bg-white/50 p-12 text-center">
          <p className="text-[#434655]">
            {debouncedSearch
              ? "No se encontraron plantillas que coincidan con su búsqueda."
              : "Aún no hay plantillas. Suba su primera plantilla para comenzar."}
          </p>
        </div>
      ) : (
        <div className="rounded-lg bg-white shadow-[0_12px_32px_rgba(25,28,30,0.06)] overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow className="bg-[#eceef0] border-b border-[rgba(195,198,215,0.2)] hover:bg-[#eceef0]">
                <TableHead className="font-semibold text-[#191c1e]">Nombre</TableHead>
                <TableHead className="font-semibold text-[#191c1e]">Descripción</TableHead>
                <TableHead className="font-semibold text-[#191c1e]">Variables</TableHead>
                <TableHead className="font-semibold text-[#191c1e]">Versión</TableHead>
                <TableHead className="font-semibold text-[#191c1e]">Creado</TableHead>
                <TableHead className="w-[70px] font-semibold text-[#191c1e]">Acciones</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.items.map((template, index) => (
                <TableRow
                  key={template.id}
                  className={`cursor-pointer border-b border-[rgba(195,198,215,0.1)] transition-colors hover:bg-[#e6e8ea]/50 ${index % 2 === 1 ? "bg-[#f7f9fb]" : ""}`}
                  onClick={() =>
                    navigate({ to: "/templates/$templateId", params: { templateId: template.id } })
                  }
                >
                  <TableCell className="font-medium text-[#191c1e]">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span>{template.name}</span>
                      {template.access_type === "shared" && (
                        <Badge className="bg-[#e8f0fe] text-[#1a56db] border-0 rounded-full text-[10px] font-semibold leading-none px-2 py-0.5">
                          Compartida
                        </Badge>
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="text-[#434655]">
                    {truncate(template.description, 50)}
                  </TableCell>
                  <TableCell>
                    <Badge className="bg-[#dbe1ff] text-[#004ac6] border-0 rounded-full font-semibold text-xs hover:bg-[#b4c5ff]">
                      {template.variables.length} var
                      {template.variables.length !== 1 ? "s" : ""}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className="border-[#2563eb]/30 text-[#004ac6] rounded-full">
                      v{template.current_version}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-[#434655]">
                    {formatDate(template.created_at)}
                  </TableCell>
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      className="text-[#434655] hover:text-[#004ac6] hover:bg-[#dbe1ff]/50"
                      onClick={(e) => {
                        e.stopPropagation();
                        navigate({
                          to: "/templates/$templateId",
                          params: { templateId: template.id },
                        });
                      }}
                    >
                      <EyeIcon className="size-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
