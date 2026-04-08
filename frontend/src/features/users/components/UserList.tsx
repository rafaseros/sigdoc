import { useState } from "react";
import { toast } from "sonner";
import { PencilIcon, UserXIcon } from "lucide-react";
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
import { useUsers, type UserResponse } from "../api";
import { useDeactivateUser } from "../api";
import { EditUserDialog } from "./EditUserDialog";

export function UserList() {
  const { data, isLoading, isError, error } = useUsers({ size: 50 });
  const deactivateMutation = useDeactivateUser();
  const [editingUser, setEditingUser] = useState<UserResponse | null>(null);
  const [confirmDeactivate, setConfirmDeactivate] = useState<string | null>(
    null
  );

  function formatDate(dateString: string) {
    return new Date(dateString).toLocaleDateString("es-ES", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  }

  async function handleDeactivate(id: string) {
    try {
      await deactivateMutation.mutateAsync(id);
      toast.success("Usuario desactivado con éxito");
      setConfirmDeactivate(null);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Error al desactivar usuario";
      toast.error(message);
    }
  }

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
          Error al cargar usuarios: {error?.message ?? "Error desconocido"}
        </div>
      ) : !data?.items.length ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-[rgba(195,198,215,0.3)] bg-white/50 p-12 text-center">
          <p className="text-[#434655]">
            No hay usuarios registrados.
          </p>
        </div>
      ) : (
        <div className="rounded-lg bg-white shadow-[0_12px_32px_rgba(25,28,30,0.06)] overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow className="bg-[#eceef0] border-b border-[rgba(195,198,215,0.2)] hover:bg-[#eceef0]">
                <TableHead className="font-semibold text-[#191c1e]">Email</TableHead>
                <TableHead className="font-semibold text-[#191c1e]">Nombre</TableHead>
                <TableHead className="font-semibold text-[#191c1e]">Rol</TableHead>
                <TableHead className="font-semibold text-[#191c1e]">Estado</TableHead>
                <TableHead className="font-semibold text-[#191c1e]">Creado</TableHead>
                <TableHead className="w-[120px] font-semibold text-[#191c1e]">Acciones</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.items.map((user, index) => (
                <TableRow key={user.id} className={`border-b border-[rgba(195,198,215,0.1)] transition-colors hover:bg-[#e6e8ea]/50 ${index % 2 === 1 ? "bg-[#f7f9fb]" : ""}`}>
                  <TableCell className="font-medium text-[#191c1e]">{user.email}</TableCell>
                  <TableCell>{user.full_name}</TableCell>
                  <TableCell>
                    <Badge
                      className={user.role === "admin" ? "bg-gradient-to-br from-[#004ac6] to-[#2563eb] text-white border-0 rounded-full" : "bg-[#dbe1ff] text-[#004ac6] border-0 rounded-full"}
                    >
                      {user.role === "admin" ? "Admin" : "Usuario"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge
                      className={user.is_active ? "bg-[#d1fae5] text-[#059669] border-0 rounded-full" : "bg-[#ffdad6] text-[#ba1a1a] border-0 rounded-full"}
                    >
                      {user.is_active ? "Activo" : "Inactivo"}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-[#434655]">
                    {formatDate(user.created_at)}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => setEditingUser(user)}
                        title="Editar"
                        className="text-[#434655] hover:text-[#004ac6] hover:bg-[#dbe1ff]/50"
                      >
                        <PencilIcon className="size-4" />
                      </Button>
                    {confirmDeactivate === user.id ? (
                      <div className="flex items-center gap-1">
                        <Button
                          variant="destructive"
                          size="sm"
                          onClick={() => handleDeactivate(user.id)}
                          disabled={deactivateMutation.isPending}
                        >
                          {deactivateMutation.isPending
                            ? "..."
                            : "Confirmar"}
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setConfirmDeactivate(null)}
                        >
                          No
                        </Button>
                      </div>
                    ) : (
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => setConfirmDeactivate(user.id)}
                        title="Desactivar"
                        disabled={!user.is_active}
                        className="text-[#434655] hover:text-[#ba1a1a] hover:bg-[#ffdad6]/50"
                      >
                        <UserXIcon className="size-4" />
                      </Button>
                    )}
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
    </div>
  );
}
