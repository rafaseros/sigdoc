import { createFileRoute, Link, Outlet, redirect, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import {
  Folder,
  Users,
  ShieldCheck,
  ChevronDown,
  KeyRound,
  LogOut,
} from "lucide-react";
import { useAuth } from "@/shared/lib/auth";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ChangePasswordDialog } from "@/features/users";
import { getRoleLabel } from "@/shared/lib/role-labels";
import { canManageUsers, canViewAudit } from "@/shared/lib/permissions";

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
  const [changePassOpen, setChangePassOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate({ to: "/login" });
  };

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-40 border-b border-[rgba(195,198,215,0.20)] bg-white/85 backdrop-blur-xl">
        <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4">
          {/* Brand + nav */}
          <div className="flex items-center gap-8">
            <Link to="/templates" className="flex items-center gap-2">
              <span className="inline-flex size-7 items-center justify-center rounded-md bg-gradient-to-br from-[#004ac6] to-[#2563eb] text-[13px] font-bold text-white shadow-[var(--shadow-brand-sm)]">
                S
              </span>
              <span className="text-[17px] font-bold tracking-tight text-[var(--fg-1)]">
                SigDoc
              </span>
            </Link>

            <nav className="flex items-center gap-1">
              <NavLink to="/templates" icon={<Folder className="size-3.5" />}>
                Plantillas
              </NavLink>
              {canManageUsers(user?.role) && (
                <NavLink to="/users" icon={<Users className="size-3.5" />}>
                  Usuarios
                </NavLink>
              )}
              {canViewAudit(user?.role) && (
                <NavLink to="/audit" icon={<ShieldCheck className="size-3.5" />}>
                  Auditoría
                </NavLink>
              )}
            </nav>
          </div>

          {/* User chip */}
          {user && <UserChip user={user} onChangePass={() => setChangePassOpen(true)} onLogout={handleLogout} />}
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6">
        <Outlet />
      </main>

      <ChangePasswordDialog open={changePassOpen} onOpenChange={setChangePassOpen} />
    </div>
  );
}

function NavLink({
  to,
  icon,
  children,
}: {
  to: "/templates" | "/users" | "/audit";
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <Link
      to={to}
      className="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium text-[var(--fg-2)] transition-all hover:bg-[var(--bg-accent)]/50 hover:text-[var(--primary)] [&.active]:bg-[var(--bg-accent)] [&.active]:text-[var(--primary)] [&.active]:font-semibold"
    >
      {icon}
      {children}
    </Link>
  );
}

function UserChip({
  user,
  onChangePass,
  onLogout,
}: {
  user: { email: string; role: string };
  onChangePass: () => void;
  onLogout: () => void;
}) {
  const initials = getInitials(user.email);
  const displayName = getDisplayName(user.email);
  const roleLabel = getRoleLabel(user.role);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <button
            type="button"
            className="group/chip inline-flex items-center gap-2 rounded-full p-1 pr-2 transition-colors hover:bg-[var(--bg-muted)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] data-[popup-open]:bg-[var(--bg-muted)]"
          />
        }
      >
        <Avatar initials={initials} />
        <span className="hidden flex-col items-start leading-none sm:flex">
          <span className="text-[12.5px] font-semibold text-[var(--fg-1)]">{displayName}</span>
          <span className="mt-0.5 text-[11px] text-[var(--fg-3)]">{roleLabel}</span>
        </span>
        <ChevronDown className="size-3.5 text-[var(--fg-3)] transition-transform group-data-[popup-open]/chip:rotate-180" />
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" sideOffset={8} className="w-64 p-1.5">
        <div className="border-b border-[rgba(195,198,215,0.20)] px-3 pb-3 pt-2">
          <div className="text-[13.5px] font-semibold text-[var(--fg-1)]">{displayName}</div>
          <div className="mt-0.5 font-mono text-[11.5px] text-[var(--fg-3)]">{user.email}</div>
          <span className="mt-2 inline-flex items-center rounded-full bg-[var(--bg-accent)] px-2 py-0.5 text-[11px] font-semibold text-[var(--primary)]">
            {roleLabel}
          </span>
        </div>

        <DropdownMenuItem onClick={onChangePass} className="mt-1 gap-2 px-3 py-2 text-sm">
          <KeyRound className="size-4 text-[var(--fg-2)]" />
          Cambiar contraseña
        </DropdownMenuItem>

        <DropdownMenuSeparator />

        <DropdownMenuItem
          onClick={onLogout}
          className="gap-2 px-3 py-2 text-sm text-[var(--destructive)] focus:bg-[var(--destructive)]/8 focus:text-[var(--destructive)]"
        >
          <LogOut className="size-4" />
          Cerrar sesión
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function Avatar({ initials }: { initials: string }) {
  return (
    <span className="inline-flex size-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-[#004ac6] to-[#2563eb] text-[12px] font-semibold text-white">
      {initials}
    </span>
  );
}

function getInitials(email: string): string {
  const local = email.split("@")[0];
  const parts = local.split(/[._-]/).filter(Boolean);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  return local.slice(0, 2).toUpperCase();
}

function getDisplayName(email: string): string {
  const local = email.split("@")[0];
  const parts = local.split(/[._-]/).filter(Boolean);
  if (parts.length >= 2) {
    return parts.slice(0, 2).map(capitalize).join(" ");
  }
  return capitalize(local);
}

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
