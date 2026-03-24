import { createFileRoute, redirect } from "@tanstack/react-router";

export const Route = createFileRoute("/_authenticated/documents/")({
  beforeLoad: () => {
    throw redirect({ to: "/templates" });
  },
});
