import { createFileRoute } from "@tanstack/react-router";
import TemplateDetail, {
  DETAIL_TABS,
  type DetailTab,
} from "@/features/templates/components/TemplateDetail";

export const Route = createFileRoute("/_authenticated/templates/$templateId")({
  // Optional `?tab=` deep link into a specific detail tab (e.g. the
  // attach-from-example flow returns to `?tab=versions`). Unknown values
  // are dropped, keeping the default Documentos tab.
  validateSearch: (search: Record<string, unknown>): { tab?: DetailTab } => {
    const tab = search.tab;
    return DETAIL_TABS.includes(tab as DetailTab)
      ? { tab: tab as DetailTab }
      : {};
  },
  component: TemplateDetailPage,
});

function TemplateDetailPage() {
  const { templateId } = Route.useParams();
  const { tab } = Route.useSearch();
  return <TemplateDetail templateId={templateId} initialTab={tab} />;
}
