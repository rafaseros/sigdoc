import { useState } from "react";
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
        <label className="flex items-center gap-2 text-sm text-[#434655] cursor-pointer select-none">
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
        className="bg-[#059669] text-white hover:bg-[#047857] transition-all"
      >
        {downloading ? "Descargando..." : "Descargar ZIP"}
      </Button>
    </>
  );
}
