import { useState } from "react";
import { ChevronDownIcon, DownloadIcon } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { buttonVariants } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import { useAuth } from "@/shared/lib/auth";
import {
  buildDownloadUrl,
  triggerBlobDownload,
  type DownloadVia,
} from "../api/queries";

interface DownloadButtonProps {
  documentId: string;
  /** Base file name used for the browser's save-as dialog (without extension). */
  baseFileName?: string;
  /** Audit context: "direct" for document owner, "share" for share-by-email recipient. */
  via?: DownloadVia;
  disabled?: boolean;
}

/**
 * Role-aware download control.
 *
 * - Admin: split-button with a caret opening a dropdown containing
 *   "Descargar como PDF" and "Descargar como Word (.docx)".
 * - Non-admin: a single plain button "Descargar PDF" — no caret, no
 *   dropdown, no Word option in the DOM.
 */
export function DownloadButton({
  documentId,
  baseFileName,
  via = "direct",
  disabled = false,
}: DownloadButtonProps) {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const [downloadingFormat, setDownloadingFormat] = useState<
    "pdf" | "docx" | null
  >(null);

  const isDownloading = downloadingFormat !== null;

  async function handleDownload(format: "pdf" | "docx") {
    setDownloadingFormat(format);
    try {
      const url = buildDownloadUrl(documentId, format, via);
      const ext = format === "pdf" ? ".pdf" : ".docx";
      const cleanBase =
        baseFileName?.replace(/\.(docx|pdf)$/i, "") ??
        `document_${documentId}`;
      const filename = `${cleanBase}${ext}`;
      await triggerBlobDownload(url, filename);
    } catch {
      toast.error("Error al descargar el documento");
    } finally {
      setDownloadingFormat(null);
    }
  }

  if (!isAdmin) {
    // Non-admin: single "Descargar PDF" button — Word option NOT in DOM
    return (
      <Button
        onClick={() => handleDownload("pdf")}
        disabled={disabled || isDownloading}
        size="sm"
        className="bg-gradient-to-br from-[#059669] to-[#10b981] font-semibold text-white shadow-[0_2px_8px_rgba(5,150,105,0.25)] hover:shadow-[0_4px_14px_rgba(5,150,105,0.35)] transition-all"
      >
        <DownloadIcon className="size-4" />
        {downloadingFormat === "pdf" ? "Descargando..." : "Descargar PDF"}
      </Button>
    );
  }

  // Admin: dropdown button for format selection
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        disabled={disabled || isDownloading}
        className={cn(
          buttonVariants({ variant: "default", size: "sm" }),
          "gap-1 bg-gradient-to-br from-[#059669] to-[#10b981] font-semibold text-white shadow-[0_2px_8px_rgba(5,150,105,0.25)] hover:shadow-[0_4px_14px_rgba(5,150,105,0.35)] transition-all",
        )}
      >
        <DownloadIcon className="size-4" />
        <span>{isDownloading ? "Descargando..." : "Descargar"}</span>
        <ChevronDownIcon className="size-3.5 opacity-70" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem
          disabled={isDownloading}
          onClick={() => handleDownload("pdf")}
        >
          <DownloadIcon className="size-4" />
          Descargar como PDF
        </DropdownMenuItem>
        <DropdownMenuItem
          disabled={isDownloading}
          onClick={() => handleDownload("docx")}
        >
          <DownloadIcon className="size-4" />
          Descargar como Word (.docx)
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
