import { useState } from "react";
import { Download } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { apiClient } from "@/shared/lib/api-client";
import { buildBulkDownloadUrl } from "../api/queries";

interface BulkDownloadControlsProps {
  batchId: string;
  isAdmin: boolean;
}

export function BulkDownloadControls({
  batchId,
  isAdmin,
}: BulkDownloadControlsProps) {
  const [downloading, setDownloading] = useState(false);
  const [includeBoth, setIncludeBoth] = useState(false);

  const handleDownload = async () => {
    setDownloading(true);
    try {
      const downloadUrl = buildBulkDownloadUrl(
        batchId,
        "pdf",
        isAdmin ? includeBoth : false,
      );
      const response = await apiClient.get(downloadUrl, {
        responseType: "blob",
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `bulk_${batchId}.zip`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      toast.error("Error al descargar el ZIP");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <>
      {isAdmin && (
        <label className="flex cursor-pointer select-none items-center gap-2 text-[13px] text-[var(--fg-2)]">
          <input
            type="checkbox"
            checked={includeBoth}
            onChange={(e) => setIncludeBoth(e.target.checked)}
            disabled={downloading}
            className="size-4 rounded accent-[#2563eb]"
          />
          Incluir documentos Word (.docx)
        </label>
      )}
      <Button
        onClick={handleDownload}
        disabled={downloading}
        className="bg-gradient-to-br from-[#059669] to-[#10b981] font-semibold text-white shadow-[0_4px_12px_rgba(5,150,105,0.30)] hover:shadow-[0_6px_18px_rgba(5,150,105,0.40)] transition-all"
      >
        <Download className="size-4" />
        {downloading ? "Descargando..." : "Descargar ZIP"}
      </Button>
    </>
  );
}
