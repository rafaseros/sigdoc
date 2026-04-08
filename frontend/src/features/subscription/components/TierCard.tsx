import {
  FileTextIcon,
  LayoutTemplateIcon,
  UsersIcon,
  ShareIcon,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { useTenantTier, type ResourceUsage } from "../api/queries";

// ─── Helpers ───────────────────────────────────────────────────────────────

function getProgressColor(percentage: number | null): string {
  if (percentage === null) return "bg-[#004ac6]";
  if (percentage >= 80) return "bg-[#ba1a1a]";
  if (percentage >= 60) return "bg-[#e6a817]";
  return "bg-[#059669]";
}

function formatLimit(limit: number | null): string {
  return limit === null ? "Sin límite" : String(limit);
}

// ─── UsageRow ──────────────────────────────────────────────────────────────

interface UsageRowProps {
  icon: React.ReactNode;
  label: string;
  usage: ResourceUsage;
}

function UsageRow({ icon, label, usage }: UsageRowProps) {
  const pct = usage.percentage_used ?? 0;
  const barColor = getProgressColor(usage.limit !== null ? pct : null);

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-sm">
        <div className="flex items-center gap-1.5 text-[#434655]">
          {icon}
          <span>{label}</span>
        </div>
        <span className="text-xs font-medium text-[#191c1e]">
          {usage.used}{usage.limit !== null ? ` / ${formatLimit(usage.limit)}` : ""}
        </span>
      </div>
      {usage.limit !== null ? (
        <div className="relative h-2 w-full overflow-hidden rounded-full bg-[#e6e8ea]">
          <div
            className={`h-full rounded-full transition-all duration-300 ${barColor}`}
            style={{ width: `${Math.min(100, pct)}%` }}
          />
        </div>
      ) : (
        <Progress value={0} className="bg-[#dbe1ff]" />
      )}
    </div>
  );
}

// ─── TierCard ──────────────────────────────────────────────────────────────

export function TierCard() {
  const { data, isLoading, isError } = useTenantTier();

  if (isLoading) {
    return (
      <Card className="w-full max-w-sm">
        <CardHeader>
          <Skeleton className="h-5 w-32" />
          <Skeleton className="h-3 w-20 mt-1" />
        </CardHeader>
        <CardContent className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="space-y-2">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-2 w-full" />
            </div>
          ))}
        </CardContent>
      </Card>
    );
  }

  if (isError || !data) {
    return null;
  }

  const { tier, usage } = data;

  const tierBadgeStyle =
    tier.slug === "enterprise"
      ? "bg-gradient-to-br from-[#004ac6] to-[#2563eb] text-white border-0 rounded-full"
      : tier.slug === "pro"
        ? "bg-[#dbe1ff] text-[#004ac6] border-0 rounded-full"
        : "bg-[#e6e8ea] text-[#434655] border-0 rounded-full";

  return (
    <Card className="w-full max-w-sm bg-white shadow-[0_12px_32px_rgba(25,28,30,0.06)]">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm text-[#191c1e]">Plan actual</CardTitle>
          <Badge className={tierBadgeStyle}>{tier.name}</Badge>
        </div>
        <CardDescription className="text-xs text-[#434655]">
          Uso de recursos este mes
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <UsageRow
          icon={<FileTextIcon className="size-3.5" />}
          label="Documentos"
          usage={usage.documents}
        />
        <UsageRow
          icon={<LayoutTemplateIcon className="size-3.5" />}
          label="Plantillas"
          usage={usage.templates}
        />
        <UsageRow
          icon={<UsersIcon className="size-3.5" />}
          label="Usuarios"
          usage={usage.users}
        />

        {tier.slug === "free" && (
          <p className="text-xs text-[#434655] pt-1 border-t border-[rgba(195,198,215,0.2)]">
            ¿Necesitás más recursos?{" "}
            <span className="text-[#004ac6] font-medium">
              Contactá al administrador para actualizar tu plan.
            </span>
          </p>
        )}
      </CardContent>
    </Card>
  );
}
