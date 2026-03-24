import { createFileRoute, Link, Outlet, redirect, useNavigate } from "@tanstack/react-router";
import { useAuth } from "@/shared/lib/auth";
import { Button } from "@/components/ui/button";
import { ChangePasswordDialog } from "@/features/users";

export const Route = createFileRoute("/_authenticated")({
  beforeLoad: () => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      throw redirect({ to: "/login" });
    }
  },
  component: AuthenticatedLayout,
});

function AuthenticatedLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate({ to: "/login" });
  };

  const isAdmin = user?.role === "admin";

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b">
        <div className="container mx-auto flex h-14 items-center justify-between px-4">
          <div className="flex items-center gap-6">
            <h1 className="text-lg font-semibold">SigDoc</h1>
            <nav className="flex items-center gap-4">
              <Link
                to="/templates"
                className="text-sm font-medium text-muted-foreground transition-colors hover:text-foreground [&.active]:text-foreground"
              >
                Plantillas
              </Link>
              {isAdmin && (
                <Link
                  to="/users"
                  className="text-sm font-medium text-muted-foreground transition-colors hover:text-foreground [&.active]:text-foreground"
                >
                  Usuarios
                </Link>
              )}
            </nav>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm text-muted-foreground">
              {user?.email ?? "Usuario"}
            </span>
            <ChangePasswordDialog />
            <Button variant="outline" size="sm" onClick={handleLogout}>
              Cerrar Sesión
            </Button>
          </div>
        </div>
      </header>
      <main className="container mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
