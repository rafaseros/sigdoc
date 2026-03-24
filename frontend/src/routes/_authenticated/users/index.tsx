import { createFileRoute } from "@tanstack/react-router";
import { UserList, CreateUserDialog } from "@/features/users";

export const Route = createFileRoute("/_authenticated/users/")({
  beforeLoad: () => {
    // Additional admin check could go here if we had access to auth context
    // The component-level check below handles the UI guard
  },
  component: UsersPage,
});

function UsersPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Usuarios</h2>
          <p className="text-muted-foreground">
            Gestione los usuarios del sistema
          </p>
        </div>
        <CreateUserDialog />
      </div>
      <UserList />
    </div>
  );
}
