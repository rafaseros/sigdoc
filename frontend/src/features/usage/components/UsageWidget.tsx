import { FileTextIcon } from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useMyUsage } from "../api/queries";
import { useTenantTier } from "@/features/subscription/api/queries";

function getCurrentYearMonth(): { year: number; month: number } {
  const now = new Date();
  return { year: now.getFullYear(), month: now.getMonth() + 1 };
}

const MONTH_NAMES = [
  "enero",
  "febrero",
  "marzo",
  "abril",
  "mayo",
  "junio",
  "julio",
  "agosto",
  "septiembre",
  "octubre",
  "noviembre",
  "diciembre",
];

function getProgressColor(pct: number): string {
  if (pct >= 80) return "bg-[#ba1a1a]";
  if (pct >= 60) return "bg-[#e6a817]";
  return "bg-[#004ac6]";
}

export function UsageWidget() {
  const { year, month } = getCurrentYearMonth();
  const { data, isLoading, isError } = useMyUsage(year, month);
  const { data: tierData } = useTenantTier();

  if (isLoading) {
    return (
      <Card className="w-full max-w-xs">
        <CardHeader>
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-3 w-24" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-10 w-16" />
          <Skeleton className="h-2 w-full mt-3" />
        </CardContent>
      </Card>
    );
  }

  if (isError) {
    return null;
  }

  const totalDocs = data?.total_documents ?? 0;
  const monthName = MONTH_NAMES[(data?.month ?? month) - 1];
  const displayYear = data?.year ?? year;

  // Tier quota context (optional — gracefully absent)
  const docUsage = tierData?.usage.documents ?? null;
  const monthlyLimit = docUsage?.limit ?? null;
  const pct = monthlyLimit !== null ? Math.min(100, (totalDocs / monthlyLimit) * 100) : 0;
  const barColor = monthlyLimit !== null ? getProgressColor(pct) : "bg-[#004ac6]";

  return (
    <Card className="w-full max-w-xs bg-white shadow-[0_12px_32px_rgba(25,28,30,0.06)]">
      <CardHeader>
        <div className="flex items-center gap-2">
          <div className="flex size-8 items-center justify-center rounded-full bg-[#dbe1ff]">
            <FileTextIcon className="size-4 text-[#004ac6]" />
          </div>
          <div>
            <CardTitle className="text-sm text-[#191c1e]">
              Documentos generados
            </CardTitle>
            <CardDescription className="text-xs capitalize">
              {monthName} {displayYear}
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <p className="text-3xl font-bold text-[#004ac6]">{totalDocs}</p>
        <p className="mt-1 text-xs text-[#434655]">
          {monthlyLimit !== null
            ? `de ${monthlyLimit} documentos este mes`
            : totalDocs === 1
              ? "documento este mes"
              : "documentos este mes"}
        </p>
        {monthlyLimit !== null && (
          <div className="mt-3 relative h-2 w-full overflow-hidden rounded-full bg-[#e6e8ea]">
            <div
              className={`h-full rounded-full transition-all duration-300 ${barColor}`}
              style={{ width: `${pct}%` }}
            />
          </div>
        )}
      </CardContent>
    </Card>
  );
}
