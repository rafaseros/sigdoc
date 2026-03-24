import { useState, useCallback } from "react";
import { useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";
import { useDropzone } from "react-dropzone";
import {
  ArrowLeft,
  FileText,
  Files,
  Trash2,
  Variable,
  Info,
  Clock,
  Upload,
} from "lucide-react";

import {
  useTemplate,
  useDeleteTemplate,
  useUploadNewVersion,
} from "@/features/templates/api";
import type { Template } from "@/features/templates/api";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

import { TemplateDetailSkeleton } from "./TemplateDetailSkeleton";

function formatFileSize(bytes: number): string {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

interface TemplateDetailProps {
  templateId: string;
}

export default function TemplateDetail({ templateId }: TemplateDetailProps) {
  const { data: template, isLoading } = useTemplate(templateId);
  const deleteTemplate = useDeleteTemplate();
  const uploadNewVersion = useUploadNewVersion();
  const navigate = useNavigate();
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      setSelectedFile(acceptedFiles[0]);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        [".docx"],
    },
    maxFiles: 1,
  });

  function handleUploadVersion() {
    if (!selectedFile) return;
    uploadNewVersion.mutate(
      { templateId, file: selectedFile },
      {
        onSuccess: () => {
          toast.success("Nueva versión subida con éxito");
          setUploadDialogOpen(false);
          setSelectedFile(null);
        },
        onError: () => {
          toast.error("Error al subir la nueva versión");
        },
      }
    );
  }

  if (isLoading) return <TemplateDetailSkeleton />;
  if (!template) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-12">
        <p className="text-muted-foreground">Plantilla no encontrada</p>
        <Button variant="outline" onClick={() => navigate({ to: "/templates" })}>
          <ArrowLeft />
          Volver a Plantillas
        </Button>
      </div>
    );
  }

  const currentVersion = template.versions.find(
    (v) => v.version === template.current_version
  );

  function handleDelete() {
    deleteTemplate.mutate(templateId, {
      onSuccess: () => {
        toast.success("Plantilla eliminada con éxito");
        navigate({ to: "/templates" });
      },
      onError: () => {
        toast.error("Error al eliminar la plantilla");
      },
    });
    setDeleteDialogOpen(false);
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start gap-4">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => navigate({ to: "/templates" })}
        >
          <ArrowLeft />
        </Button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold">{template.name}</h1>
          {template.description && (
            <p className="mt-1 text-muted-foreground">{template.description}</p>
          )}
        </div>
      </div>

      {/* Action Bar */}
      <div className="flex flex-wrap gap-2">
        {currentVersion && (
          <>
            <Button
              onClick={() =>
                navigate({
                  to: "/documents/generate/$versionId",
                  params: { versionId: currentVersion.id },
                  search: { templateId },
                })
              }
            >
              <FileText />
              Generar Documento
            </Button>
            <Button
              variant="outline"
              onClick={() =>
                navigate({
                  to: "/documents/bulk/$versionId",
                  params: { versionId: currentVersion.id },
                  search: { templateId },
                })
              }
            >
              <Files />
              Generación Masiva
            </Button>
          </>
        )}

        <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
          <DialogTrigger
            render={
              <Button variant="destructive">
                <Trash2 />
                Eliminar Plantilla
              </Button>
            }
          />
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Eliminar Plantilla</DialogTitle>
              <DialogDescription>
                ¿Está seguro de que desea eliminar "{template.name}"? Esta acción
                no se puede deshacer. Todas las versiones serán eliminadas permanentemente.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setDeleteDialogOpen(false)}
              >
                Cancelar
              </Button>
              <Button
                variant="destructive"
                onClick={handleDelete}
                disabled={deleteTemplate.isPending}
              >
                {deleteTemplate.isPending ? "Eliminando..." : "Eliminar"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="info">
        <TabsList>
          <TabsTrigger value="info">
            <Info className="size-3.5" />
            Información
          </TabsTrigger>
          <TabsTrigger value="variables">
            <Variable className="size-3.5" />
            Variables
          </TabsTrigger>
          <TabsTrigger value="versions">
            <Clock className="size-3.5" />
            Versiones
          </TabsTrigger>
        </TabsList>

        {/* Info Tab */}
        <TabsContent value="info">
          <Card>
            <CardHeader>
              <CardTitle>Información de la Plantilla</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-3">
                <dt className="text-muted-foreground">Versión Actual</dt>
                <dd className="font-medium">v{template.current_version}</dd>

                <dt className="text-muted-foreground">Creado</dt>
                <dd>{formatDate(template.created_at)}</dd>

                <dt className="text-muted-foreground">Actualizado</dt>
                <dd>{formatDate(template.updated_at)}</dd>

                {currentVersion && (
                  <>
                    <dt className="text-muted-foreground">Tamaño del Archivo</dt>
                    <dd>{formatFileSize(currentVersion.file_size)}</dd>
                  </>
                )}

                <dt className="text-muted-foreground">Total de Versiones</dt>
                <dd>{template.versions.length}</dd>
              </dl>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Variables Tab */}
        <TabsContent value="variables">
          <Card>
            <CardHeader>
              <CardTitle>Variables de la Plantilla</CardTitle>
            </CardHeader>
            <CardContent>
              {template.variables.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {template.variables.map((variable) => (
                    <Badge key={variable} variant="secondary">
                      {variable}
                    </Badge>
                  ))}
                </div>
              ) : (
                <p className="text-muted-foreground">
                  No se encontraron variables en esta plantilla.
                </p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Versions Tab */}
        <TabsContent value="versions">
          <div className="space-y-3">
            <Dialog
              open={uploadDialogOpen}
              onOpenChange={setUploadDialogOpen}
            >
              <DialogTrigger
                render={
                  <Button>
                    <Upload className="size-4" />
                    Subir Nueva Versión
                  </Button>
                }
              />
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Subir Nueva Versión</DialogTitle>
                  <DialogDescription>
                    Suba un nuevo archivo .docx para crear la versión v
                    {template.current_version + 1} de "{template.name}".
                  </DialogDescription>
                </DialogHeader>
                <div
                  {...getRootProps()}
                  className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 transition-colors ${
                    isDragActive
                      ? "border-primary bg-primary/5"
                      : "border-muted-foreground/25 hover:border-muted-foreground/50"
                  }`}
                >
                  <input {...getInputProps()} />
                  <Upload className="mb-2 size-8 text-muted-foreground" />
                  {selectedFile ? (
                    <p className="text-sm font-medium">{selectedFile.name}</p>
                  ) : isDragActive ? (
                    <p className="text-sm text-muted-foreground">
                      Suelte el archivo aquí...
                    </p>
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      Arrastre y suelte un archivo .docx, o haga clic para seleccionar
                    </p>
                  )}
                </div>
                <DialogFooter>
                  <Button
                    variant="outline"
                    onClick={() => {
                      setUploadDialogOpen(false);
                      setSelectedFile(null);
                    }}
                  >
                    Cancelar
                  </Button>
                  <Button
                    onClick={handleUploadVersion}
                    disabled={!selectedFile || uploadNewVersion.isPending}
                  >
                    {uploadNewVersion.isPending
                      ? "Subiendo..."
                      : "Subir Versión"}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>

            {template.versions
              .sort((a, b) => b.version - a.version)
              .map((version) => (
                <Card key={version.id} size="sm">
                  <CardContent>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <Badge
                          variant={
                            version.version === template.current_version
                              ? "default"
                              : "outline"
                          }
                        >
                          v{version.version}
                        </Badge>
                        <span className="text-muted-foreground">
                          {version.variables.length} variable
                          {version.variables.length !== 1 ? "s" : ""}
                        </span>
                        <span className="text-muted-foreground">
                          {formatFileSize(version.file_size)}
                        </span>
                      </div>
                      <span className="text-sm text-muted-foreground">
                        {formatDate(version.created_at)}
                      </span>
                    </div>
                  </CardContent>
                </Card>
              ))}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
