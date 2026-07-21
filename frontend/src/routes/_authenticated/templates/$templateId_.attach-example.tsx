import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowLeft } from "lucide-react";

import { AttachFromExamplePage } from "@/features/templates/components/AttachFromExamplePage";

// `$templateId_` (trailing underscore) keeps this a SIBLING of the
// $templateId detail route — the detail component renders no <Outlet />, so
// nesting under it would never display this page.
export const Route = createFileRoute(
  "/_authenticated/templates/$templateId_/attach-example",
)({
  component: AttachExampleRoute,
});

function AttachExampleRoute() {
  const { templateId } = Route.useParams();
  // Permission guard (owner/admin) lives inside AttachFromExamplePage — it
  // needs the template detail data anyway; the backend re-validates.
  return (
    <div className="space-y-5">
      <Link
        to="/templates/$templateId"
        params={{ templateId }}
        className="-ml-1 inline-flex items-center gap-1 text-[12.5px] font-medium text-[var(--fg-3)] transition-colors hover:text-[var(--primary)]"
      >
        <ArrowLeft className="size-3.5" />
        Volver a la plantilla
      </Link>
      <AttachFromExamplePage templateId={templateId} />
    </div>
  );
}
