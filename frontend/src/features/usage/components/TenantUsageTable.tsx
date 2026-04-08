import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { useTenantUsage } from "../api/queries";

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

export function TenantUsageTable() {
  const { year, month } = getCurrentYearMonth();
  const { data, isLoading, isError, error } = useTenantUsage(year, month);

  const monthName = MONTH_NAMES[month - 1];

  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <div className="rounded-lg border border-destructive/50 bg-destructive/5 p-4 text-sm text-destructive">
        Error al cargar el uso del tenant: {error?.message ?? "Error desconocido"}
      </div>
    );
  }

  const users = data?.by_user ?? [];

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm text-[#434655]">
          Uso por usuario —{" "}
          <span className="capitalize font-medium text-[#191c1e]">
            {monthName} {year}
          </span>
        </p>
        <p className="text-sm font-semibold text-[#004ac6]">
          Total: {data?.total_documents ?? 0} documentos
        </p>
      </div>

      {users.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-[rgba(195,198,215,0.3)] bg-white/50 p-10 text-center">
          <p className="text-sm text-[#434655]">
            No se generaron documentos este mes.
          </p>
        </div>
      ) : (
        <div className="rounded-lg bg-white shadow-[0_12px_32px_rgba(25,28,30,0.06)] overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow className="bg-[#eceef0] border-b border-[rgba(195,198,215,0.2)] hover:bg-[#eceef0]">
                <TableHead className="font-semibold text-[#191c1e]">
                  Usuario
                </TableHead>
                <TableHead className="font-semibold text-[#191c1e]">
                  Email
                </TableHead>
                <TableHead className="font-semibold text-[#191c1e] text-right">
                  Documentos
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map((user, index) => (
                <TableRow
                  key={user.user_id}
                  className={`border-b border-[rgba(195,198,215,0.1)] transition-colors hover:bg-[#e6e8ea]/50 ${
                    index % 2 === 1 ? "bg-[#f7f9fb]" : ""
                  }`}
                >
                  <TableCell className="font-medium text-[#191c1e]">
                    {user.full_name ?? "—"}
                  </TableCell>
                  <TableCell className="text-[#434655]">
                    {user.user_email}
                  </TableCell>
                  <TableCell className="text-right font-semibold text-[#004ac6]">
                    {user.document_count}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
