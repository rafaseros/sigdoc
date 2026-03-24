import { createFileRoute } from "@tanstack/react-router";
import TemplateDetail from "@/features/templates/components/TemplateDetail";

export const Route = createFileRoute("/_authenticated/templates/$templateId")({
  component: TemplateDetailPage,
});

function TemplateDetailPage() {
  const { templateId } = Route.useParams();
  return <TemplateDetail templateId={templateId} />;
}
