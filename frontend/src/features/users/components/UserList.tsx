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
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed p-12 text-center">
          <p className="text-muted-foreground">
            No hay usuarios registrados.
          </p>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Email</TableHead>
              <TableHead>Nombre</TableHead>
              <TableHead>Rol</TableHead>
              <TableHead>Estado</TableHead>
              <TableHead>Creado</TableHead>
              <TableHead className="w-[120px]">Acciones</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.items.map((user) => (
              <TableRow key={user.id}>
                <TableCell className="font-medium">{user.email}</TableCell>
                <TableCell>{user.full_name}</TableCell>
                <TableCell>
                  <Badge
                    variant={user.role === "admin" ? "default" : "secondary"}
                  >
                    {user.role === "admin" ? "Admin" : "Usuario"}
                  </Badge>
                </TableCell>
                <TableCell>
                  <Badge
                    variant={user.is_active ? "default" : "destructive"}
                  >
                    {user.is_active ? "Activo" : "Inactivo"}
                  </Badge>
                </TableCell>
                <TableCell className="text-muted-foreground">
                  {formatDate(user.created_at)}
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      onClick={() => setEditingUser(user)}
                      title="Editar"
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
