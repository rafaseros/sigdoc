import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { toast } from "sonner";
import { UploadIcon, FileIcon, XIcon } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useUploadTemplate } from "../api";

export function UploadTemplateDialog() {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [file, setFile] = useState<File | null>(null);

  const uploadMutation = useUploadTemplate();

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      const selected = acceptedFiles[0];
      setFile(selected);
      if (!name) {
        setName(selected.name.replace(/\.docx$/, ""));
      }
    }
  }, [name]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        [".docx"],
    },
    maxFiles: 1,
  });

  function resetForm() {
    setName("");
    setDescription("");
    setFile(null);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    if (!file) {
      toast.error("Por favor seleccione un archivo .docx");
      return;
    }

    if (!name.trim()) {
      toast.error("El nombre de la plantilla es obligatorio");
      return;
    }

    try {
      await uploadMutation.mutateAsync({
        file,
        name: name.trim(),
        description: description.trim() || undefined,
      });
      toast.success("Plantilla subida con éxito");
      resetForm();
      setOpen(false);
    } catch (error: unknown) {
      const message =
        error instanceof Error ? error.message : "Error al subir la plantilla";
      toast.error(message);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={setOpen}
    >
      <DialogTrigger
        render={<Button />}
      >
        <UploadIcon className="size-4 mr-2" />
        Subir Plantilla
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Subir Plantilla</DialogTitle>
            <DialogDescription>
              Suba una plantilla .docx con marcadores {"{{ variable }}"}.
              Use la sintaxis {"{{ nombre_variable }}"} con espacios dentro de las llaves.{" "}
Cierre este diálogo y haga clic en &quot;Guía de Plantillas&quot; para instrucciones detalladas.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="template-name">Nombre *</Label>
              <Input
                id="template-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Ej. Contrato de Trabajo"
                required
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="template-description">Descripción</Label>
              <Textarea
                id="template-description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Descripción opcional de esta plantilla"
                rows={3}
              />
            </div>

            <div className="grid gap-2">
              <Label>Archivo *</Label>
              {file ? (
                <div className="flex items-center gap-2 rounded-lg border border-input p-3">
                  <FileIcon className="size-4 text-muted-foreground" />
                  <span className="flex-1 truncate text-sm">{file.name}</span>
                  <span className="text-xs text-muted-foreground">
                    {(file.size / 1024).toFixed(1)} KB
                  </span>
                  <button
                    type="button"
                    onClick={() => setFile(null)}
                    className="text-muted-foreground hover:text-foreground"
                  >
                    <XIcon className="size-4" />
                  </button>
                </div>
              ) : (
                <div
                  {...getRootProps()}
                  className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-6 transition-colors ${
                    isDragActive
                      ? "border-ring bg-ring/5"
                      : "border-input hover:border-ring/50"
                  }`}
                >
                  <input {...getInputProps()} />
                  <UploadIcon className="size-8 text-muted-foreground mb-2" />
                  <p className="text-sm text-muted-foreground">
                    {isDragActive
                      ? "Suelte el archivo aquí"
                      : "Arrastre y suelte un archivo .docx, o haga clic para seleccionar"}
                  </p>
                </div>
              )}
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                resetForm();
                setOpen(false);
              }}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={uploadMutation.isPending}>
              {uploadMutation.isPending ? "Subiendo..." : "Subir"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
