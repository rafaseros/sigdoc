import { FileText } from "lucide-react";

import { DownloadButton } from "./DownloadButton";

export interface GeneratedDocumentInfo {
  documentId: string;
  fileName: string;
}

/**
 * Row list for the post-generate success surface when one generate call
 * produced SEVERAL documents (a version with related files). Primary first,
 * then related documents in position order — the caller passes them in the
 * order the backend returned them.
 */
export function GeneratedDocumentsList({
  documents,
}: {
  documents: GeneratedDocumentInfo[];
}) {
  return (
    <ul className="m-0 flex list-none flex-col gap-2 p-0">
      {documents.map((doc) => (
        <li
          key={doc.documentId}
          className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-white/60 px-3 py-2"
        >
          <span className="flex min-w-0 items-center gap-2">
            <FileText className="size-4 shrink-0 text-[#059669]" />
            <span className="truncate text-[13px] font-medium text-[#065f46]">
              {doc.fileName}
            </span>
          </span>
          <DownloadButton
            documentId={doc.documentId}
            baseFileName={doc.fileName}
            via="direct"
          />
        </li>
      ))}
    </ul>
  );
}
