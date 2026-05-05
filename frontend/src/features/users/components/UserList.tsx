import { useEffect, useMemo, useState } from "react";
import { Pencil, Search, UserX } from "lucide-react";
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
import { ROLE_LABELS } from "@/shared/lib/role-labels";
import { useUsers, type UserResponse } from "../api";
import { EditUserDialog } from "./EditUserDialog";
import { DeactivateUserDialog } from "./DeactivateUserDialog";

function getInitials(email: string) {
  const local = email.split("@")[0] ?? email;
  const parts = local.split(/[._-]/).filter(Boolean);
  const first = parts[0]?.[0] ?? "?";
  const second = parts[1]?.[0] ?? parts[0]?.[1] ?? "";
  return (first + second).toUpperCase();
}

function rolePillClasses(role: string) {
  if (role === "admin") {
    return "bg-gradient-to-br from-[#004ac6] to-[#2563eb] text-white border-0 rounded-full";
  }
  if (role === "template_creator") {
    return "bg-[var(--bg-accent)] text-[var(--primary)] border-0 rounded-full hover:bg-[var(--bg-accent)]";
  }
  return "bg-[var(--bg-muted)] text-[var(--fg-2)] border-0 rounded-full hover:bg-[var(--bg-muted)]";
}

function roleLabel(role: string) {
  return ROLE_LABELS[role as keyof typeof ROLE_LABELS] ?? role;
}

export function UserList() {
  const { data, isLoading, isError, error } = useUsers({ size: 100 });
  const [editingUser, setEditingUser] = useState<UserResponse | null>(null);
  const [deactivatingUser, setDeactivatingUser] = useState<UserResponse | null>(
    null,
  );
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  const items = data?.items ?? [];

  const filtered = useMemo(() => {
    const q = debouncedSearch.trim().toLowerCase();
    if (!q) return items;
    return items.filter(
      (u) =>
        u.email.toLowerCase().includes(q) ||
        u.full_name.toLowerCase().includes(q),
    );
  }, [items, debouncedSearch]);

  function formatDate(dateString: string) {
    return new Date(dateString).toLocaleDateString("es-ES", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  }

  return (
    <div className="space-y-4">
      {/* Search row */}
      <div className="flex items-center justify-between gap-3">
        <div className="relative w-full max-w-sm">
          <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-[var(--fg-3)]" />
          <Input
            placeholder="Buscar por nombre o correo..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        {!isLoading && !isError && items.length > 0 && (
          <div className="text-xs text-[var(--fg-3)]">
            {filtered.length} de {items.length}{" "}
            {items.length === 1 ? "usuario" : "usuarios"}
          </div>
        )}
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-14 w-full rounded-lg" />
          ))}
        </div>
      ) : isError ? (
        <div className="rounded-[10px] bg-[#ffdad6] px-3.5 py-3 text-[13px] leading-[1.45] text-[#93000a]">
          Error al cargar usuarios: {error?.message ?? "Error desconocido"}
        </div>
      ) : !filtered.length ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-[rgba(195,198,215,0.4)] bg-white/50 p-12 text-center">
          <p className="text-[var(--fg-2)]">
            {debouncedSearch
              ? "No se encontraron usuarios que coincidan con su búsqueda."
              : "No hay usuarios registrados."}
          </p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl bg-white shadow-[var(--shadow-sm)] ring-1 ring-[rgba(195,198,215,0.30)]">
          <Table>
            <TableHeader>
              <TableRow className="border-b border-[rgba(195,198,215,0.2)] bg-[var(--bg-muted)] hover:bg-[var(--bg-muted)]">
                <TableHead className="font-semibold text-[var(--fg-1)]">
                  Usuario
                </TableHead>
                <TableHead className="font-semibold text-[var(--fg-1)]">
                  Rol
                </TableHead>
                <TableHead className="font-semibold text-[var(--fg-1)]">
                  Estado
                </TableHead>
                <TableHead className="font-semibold text-[var(--fg-1)]">
                  Creado
                </TableHead>
                <TableHead className="w-[120px] text-right font-semibold text-[var(--fg-1)]">
                  Acciones
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((user) => (
                <TableRow
                  key={user.id}
                  className="border-b border-[rgba(195,198,215,0.1)] transition-colors hover:bg-[var(--bg-page)]"
                >
                  <TableCell className="py-3">
                    <div className="flex items-center gap-3">
                      <span className="inline-flex size-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-[#004ac6] to-[#2563eb] text-[11px] font-semibold text-white">
                        {getInitials(user.email)}
                      </span>
                      <div className="min-w-0">
                        <div className="truncate text-sm font-semibold text-[var(--fg-1)]">
                          {user.full_name}
                        </div>
                        <div className="truncate font-mono text-[11.5px] text-[var(--fg-3)]">
                          {user.email}
                        </div>
                      </div>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge className={rolePillClasses(user.role)}>
                      {roleLabel(user.role)}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge
                      className={
                        user.is_active
                          ? "rounded-full border-0 bg-[#d1fae5] text-[#065f46] hover:bg-[#d1fae5]"
                          : "rounded-full border-0 bg-[#ffdad6] text-[#93000a] hover:bg-[#ffdad6]"
                      }
                    >
                      <span
                        className={`mr-1.5 inline-block size-1.5 rounded-full ${
                          user.is_active ? "bg-[#065f46]" : "bg-[#93000a]"
                        }`}
                      />
                      {user.is_active ? "Activo" : "Inactivo"}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-sm text-[var(--fg-3)]">
                    {formatDate(user.created_at)}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => setEditingUser(user)}
                        title="Editar"
                        className="text-[var(--fg-2)] hover:bg-[var(--bg-accent)]/60 hover:text-[var(--primary)]"
                      >
                        <Pencil className="size-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => setDeactivatingUser(user)}
                        title="Desactivar"
                        disabled={!user.is_active}
                        className="text-[var(--fg-2)] hover:bg-[#ffdad6]/50 hover:text-[var(--destructive)]"
                      >
                        <UserX className="size-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {editingUser && (
        <EditUserDialog
          user={editingUser}
          open={!!editingUser}
          onOpenChange={(open) => {
            if (!open) setEditingUser(null);
          }}
        />
      )}

      {deactivatingUser && (
        <DeactivateUserDialog
          user={deactivatingUser}
          candidates={items}
          open={!!deactivatingUser}
          onOpenChange={(open) => {
            if (!open) setDeactivatingUser(null);
          }}
        />
      )}
    </div>
  );
}
