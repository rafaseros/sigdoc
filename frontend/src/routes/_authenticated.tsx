import { createFileRoute, Link, Outlet, redirect, useNavigate } from "@tanstack/react-router";
import { useAuth } from "@/shared/lib/auth";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ChangePasswordDialog } from "@/features/users";
import { getRoleLabel } from "@/shared/lib/role-labels";

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
    <div className="min-h-screen">
      <header className="bg-[#f2f4f6]/80 backdrop-blur-sm border-b border-[rgba(195,198,215,0.15)]">
        <div className="container mx-auto flex h-14 items-center justify-between px-4">
          <div className="flex items-center gap-6">
            <h1 className="text-lg font-bold tracking-tight text-[#004ac6]">SigDoc</h1>
            <nav className="flex items-center gap-1">
              <Link
                to="/templates"
                className="text-sm font-medium text-[#434655] transition-all px-3 py-1.5 rounded-full hover:bg-[#dbe1ff]/50 hover:text-[#004ac6] [&.active]:bg-[#dbe1ff] [&.active]:text-[#004ac6]"
              >
                Plantillas
              </Link>
              {isAdmin && (
                <Link
                  to="/users"
                  className="text-sm font-medium text-[#434655] transition-all px-3 py-1.5 rounded-full hover:bg-[#dbe1ff]/50 hover:text-[#004ac6] [&.active]:bg-[#dbe1ff] [&.active]:text-[#004ac6]"
                >
                  Usuarios
                </Link>
              )}
              {isAdmin && (
                <Link
                  to="/audit"
                  className="text-sm font-medium text-[#434655] transition-all px-3 py-1.5 rounded-full hover:bg-[#dbe1ff]/50 hover:text-[#004ac6] [&.active]:bg-[#dbe1ff] [&.active]:text-[#004ac6]"
                >
                  Auditoría
                </Link>
              )}
            </nav>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm text-[#434655]">
              {user?.email ?? "Usuario"}
            </span>
            <Badge variant="secondary" className="text-xs">
              {getRoleLabel(user?.role)}
            </Badge>
            <ChangePasswordDialog />
            <Button variant="outline" size="sm" onClick={handleLogout} className="border-[rgba(195,198,215,0.3)] hover:bg-[#e6e8ea] text-[#434655]">
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
