import { createFileRoute } from "@tanstack/react-router";
import { DocumentList } from "@/features/documents";

export const Route = createFileRoute("/_authenticated/documents/")({
  component: DocumentsPage,
});

function DocumentsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Documentos Generados</h2>
        <p className="text-muted-foreground">
          Consulte, descargue o elimine los documentos generados
        </p>
      </div>
      <DocumentList />
    </div>
  );
}
