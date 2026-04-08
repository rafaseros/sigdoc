import { createFileRoute } from "@tanstack/react-router";
import { UserList, CreateUserDialog } from "@/features/users";
import { Badge } from "@/components/ui/badge";
import { useTenantTier } from "@/features/subscription/api/queries";

export const Route = createFileRoute("/_authenticated/users/")({
  beforeLoad: () => {
    // Additional admin check could go here if we had access to auth context
    // The component-level check below handles the UI guard
  },
  component: UsersPage,
});

function UsersPage() {
  const { data: tierData } = useTenantTier();
  const userUsage = tierData?.usage.users ?? null;

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
          {userUsage !== null && (
            <Badge
              className={
                userUsage.near_limit
                  ? "bg-[#ffdad6] text-[#ba1a1a] border-0 rounded-full"
                  : "bg-[#dbe1ff] text-[#004ac6] border-0 rounded-full"
              }
            >
              {userUsage.used}
              {userUsage.limit !== null ? ` / ${userUsage.limit}` : ""} usuarios
            </Badge>
          )}
        </div>
        <CreateUserDialog />
      </div>
      <UserList />
    </div>
  );
}
