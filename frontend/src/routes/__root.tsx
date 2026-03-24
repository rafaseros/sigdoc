import { createRootRoute, Outlet, useRouter } from "@tanstack/react-router";
import { Toaster } from "sonner";

export const Route = createRootRoute({
  component: () => (
    <>
      <Outlet />
      <Toaster richColors position="top-right" />
    </>
  ),
  notFoundComponent: () => {
    const router = useRouter();
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4">
        <h1 className="text-4xl font-bold">404</h1>
        <p className="text-muted-foreground">Página no encontrada</p>
        <button
          className="text-sm underline"
          onClick={() => router.navigate({ to: "/" })}
        >
          Ir al inicio
        </button>
      </div>
    );
  },
});
