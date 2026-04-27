import { createFileRoute } from "@tanstack/react-router";
import { UserList, CreateUserDialog, useUsers } from "@/features/users";
import { Badge } from "@/components/ui/badge";

export const Route = createFileRoute("/_authenticated/users/")({
  beforeLoad: () => {
    // Additional admin check could go here if we had access to auth context
    // The component-level check below handles the UI guard
  },
  component: UsersPage,
});

function UsersPage() {
  const { data } = useUsers();
  const userCount = data?.total ?? data?.items.length ?? 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div>
            <h2 className="text-2xl font-bold">Usuarios</h2>
            <p className="text-muted-foreground">
              Gestione los usuarios del sistema
            </p>
          </div>
          <Badge className="bg-[#dbe1ff] text-[#004ac6] border-0 rounded-full">
            {userCount} usuarios
          </Badge>
        </div>
        <CreateUserDialog />
      </div>
      <UserList />
    </div>
  );
}
