import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Check, LoaderCircle } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import { useFolders } from "../api/folders";
import { useUpdateTemplate } from "../api/mutations";

const NO_FOLDER_VALUE = "none";

interface MoveToFolderDialogProps {
  templateId: string;
  templateName: string;
  currentFolderId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * Resolve the initial/re-synced <Select> value for the dialog.
 *
 * `currentFolderId` may point at a folder that is not (or no longer) among
 * the caller's own folders — e.g. an orphaned reference left over from an
 * ownership change. In that case we must seed the state as
 * `NO_FOLDER_VALUE` rather than the raw id: otherwise `SelectValue`'s
 * fallback would render "Sin carpeta" (because the id has no matching
 * label) while a same-folder submit would silently re-send the
 * unresolvable id, which the backend 404s for what looks like a no-op.
 *
 * When `folders` hasn't loaded yet (`undefined`), we cannot tell whether
 * the id is orphaned, so we keep the raw id — the effect re-runs once
 * `folders` resolves and corrects the state if needed.
 */
function resolveFolderSelectValue(
  currentFolderId: string | null,
  folders: { id: string }[] | undefined,
): string {
  if (currentFolderId == null) return NO_FOLDER_VALUE;
  if (folders !== undefined && !folders.some((f) => f.id === currentFolderId)) {
    return NO_FOLDER_VALUE;
  }
  return currentFolderId;
}

export function MoveToFolderDialog({
  templateId,
  templateName,
  currentFolderId,
  open,
  onOpenChange,
}: MoveToFolderDialogProps) {
  const { data: folders } = useFolders();
  const [folderId, setFolderId] = useState<string>(() =>
    resolveFolderSelectValue(currentFolderId, folders),
  );

  // Re-sync the draft selection whenever the dialog (re)opens, or once the
  // folders list resolves, so a stale pick from a previous open doesn't
  // leak into a fresh one and an orphaned currentFolderId gets corrected
  // to NO_FOLDER_VALUE as soon as we can tell it's not in the list.
  useEffect(() => {
    if (open) setFolderId(resolveFolderSelectValue(currentFolderId, folders));
  }, [open, currentFolderId, folders]);

  const updateTemplate = useUpdateTemplate();

  // Base UI's <SelectValue> does not automatically resolve the trigger's
  // display text to the matching <SelectItem>'s rendered children unless an
  // `items` map is passed to <Select.Root> — without it, it falls back to
  // stringifying the raw value (the folder's uuid). Resolving the label
  // ourselves via a render function sidesteps that entirely.
  const folderLabelById = new Map<string, string>([
    [NO_FOLDER_VALUE, "Sin carpeta"],
    ...(folders ?? []).map((folder): [string, string] => [
      folder.id,
      folder.name,
    ]),
  ]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    updateTemplate.mutate(
      {
        templateId,
        folder_id: folderId === NO_FOLDER_VALUE ? null : folderId,
      },
      {
        onSuccess: () => {
          toast.success("Plantilla movida con éxito");
          onOpenChange(false);
        },
        onError: (err: unknown) => {
          const detail =
            err &&
            typeof err === "object" &&
            "response" in err &&
            (err as { response?: { data?: { detail?: string } } }).response
              ?.data?.detail;
          toast.error((detail as string) || "Error al mover la plantilla");
        },
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Mover a carpeta</DialogTitle>
            <DialogDescription>
              Elija la carpeta destino para "{templateName}".
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-1.5 py-4">
            <Label className="text-[12.5px] font-medium text-[var(--fg-2)]">
              Carpeta
            </Label>
            <Select
              value={folderId}
              onValueChange={(v) => setFolderId(v ?? NO_FOLDER_VALUE)}
            >
              <SelectTrigger>
                <SelectValue>
                  {(v: unknown) =>
                    folderLabelById.get(v as string) ?? "Sin carpeta"
                  }
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NO_FOLDER_VALUE}>Sin carpeta</SelectItem>
                {(folders ?? []).map((folder) => (
                  <SelectItem key={folder.id} value={folder.id}>
                    {folder.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancelar
            </Button>
            <Button
              type="submit"
              disabled={updateTemplate.isPending}
              className="bg-gradient-to-br from-[#004ac6] to-[#2563eb] font-semibold text-white shadow-[var(--shadow-brand-sm)] hover:shadow-[var(--shadow-brand-md)]"
            >
              {updateTemplate.isPending ? (
                <>
                  <LoaderCircle className="mr-2 size-4 animate-spin" />
                  Moviendo...
                </>
              ) : (
                <>
                  <Check className="mr-2 size-4" />
                  Mover
                </>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
