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
        <SearchIcon className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="Buscar plantillas..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-9"
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
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed p-12 text-center">
          <p className="text-muted-foreground">
            {debouncedSearch
              ? "No se encontraron plantillas que coincidan con su búsqueda."
              : "Aún no hay plantillas. Suba su primera plantilla para comenzar."}
          </p>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Nombre</TableHead>
              <TableHead>Descripción</TableHead>
              <TableHead>Variables</TableHead>
              <TableHead>Versión</TableHead>
              <TableHead>Creado</TableHead>
              <TableHead className="w-[70px]">Acciones</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.items.map((template) => (
              <TableRow
                key={template.id}
                className="cursor-pointer"
                onClick={() =>
                  navigate({ to: "/templates/$templateId", params: { templateId: template.id } })
                }
              >
                <TableCell className="font-medium">{template.name}</TableCell>
                <TableCell className="text-muted-foreground">
                  {truncate(template.description, 50)}
                </TableCell>
                <TableCell>
                  <Badge variant="secondary">
                    {template.variables.length} var
                    {template.variables.length !== 1 ? "s" : ""}
                  </Badge>
                </TableCell>
                <TableCell>v{template.current_version}</TableCell>
                <TableCell className="text-muted-foreground">
                  {formatDate(template.created_at)}
                </TableCell>
                <TableCell>
                  <Button
                    variant="ghost"
                    size="icon-sm"
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
      )}
    </div>
  );
}
