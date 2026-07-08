import { useState } from "react";
import { FolderPlus, Pencil, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useFolders, type Folder } from "../api/folders";
import { CreateFolderDialog } from "./CreateFolderDialog";
import { RenameFolderDialog } from "./RenameFolderDialog";
import { DeleteFolderDialog } from "./DeleteFolderDialog";

/**
 * `undefined` = "Todas" (no filter), `"none"` = "Sin carpeta" (unfiled),
 * any other string = a folder id.
 */
export type FolderFilter = string | undefined;

interface FolderSidebarProps {
  activeFolder: FolderFilter;
  onSelectFolder: (folder: FolderFilter) => void;
  /** Total template count, shown next to "Todas" only when it's cheaply known (already fetched). */
  totalCount?: number;
}

function NavRow({
  label,
  active,
  onClick,
  count,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
  count?: number;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      aria-label={label}
      className={`flex items-center justify-between gap-2 rounded-lg px-2.5 py-2 text-left text-sm transition-colors ${
        active
          ? "bg-[var(--bg-accent)] font-semibold text-[var(--primary)]"
          : "text-[var(--fg-2)] hover:bg-[var(--bg-muted)]"
      }`}
    >
      <span className="truncate">{label}</span>
      {count != null && (
        <span
          className={`shrink-0 rounded-full px-1.5 text-[10.5px] font-semibold ${
            active
              ? "bg-white text-[var(--primary)]"
              : "bg-[var(--bg-muted)] text-[var(--fg-3)]"
          }`}
        >
          {count}
        </span>
      )}
    </button>
  );
}

function FolderRow({
  folder,
  active,
  onSelect,
  onRename,
  onDelete,
}: {
  folder: Folder;
  active: boolean;
  onSelect: () => void;
  onRename: () => void;
  onDelete: () => void;
}) {
  return (
    <div className="group flex items-center gap-0.5">
      <button
        type="button"
        onClick={onSelect}
        aria-pressed={active}
        aria-label={folder.name}
        className={`flex min-w-0 flex-1 items-center justify-between gap-2 rounded-lg px-2.5 py-2 text-left text-sm transition-colors ${
          active
            ? "bg-[var(--bg-accent)] font-semibold text-[var(--primary)]"
            : "text-[var(--fg-2)] hover:bg-[var(--bg-muted)]"
        }`}
      >
        <span className="truncate">{folder.name}</span>
        <span
          className={`shrink-0 rounded-full px-1.5 text-[10.5px] font-semibold ${
            active
              ? "bg-white text-[var(--primary)]"
              : "bg-[var(--bg-muted)] text-[var(--fg-3)]"
          }`}
        >
          {folder.template_count}
        </span>
      </button>
      <div className="flex shrink-0 gap-0.5 opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          aria-label={`Renombrar carpeta ${folder.name}`}
          title="Renombrar"
          onClick={onRename}
          className="size-7 text-[var(--fg-3)] hover:bg-[var(--bg-accent)]/60 hover:text-[var(--primary)]"
        >
          <Pencil className="size-3.5" />
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          aria-label={`Eliminar carpeta ${folder.name}`}
          title="Eliminar"
          onClick={onDelete}
          className="size-7 text-[var(--fg-3)] hover:bg-[#ffdad6]/50 hover:text-[var(--destructive)]"
        >
          <Trash2 className="size-3.5" />
        </Button>
      </div>
    </div>
  );
}

export function FolderSidebar({
  activeFolder,
  onSelectFolder,
  totalCount,
}: FolderSidebarProps) {
  const { data: folders } = useFolders();
  const [createOpen, setCreateOpen] = useState(false);
  const [renamingFolder, setRenamingFolder] = useState<Folder | null>(null);
  const [deletingFolder, setDeletingFolder] = useState<Folder | null>(null);

  return (
    <nav
      aria-label="Carpetas"
      className="flex flex-col gap-0.5 lg:sticky lg:top-20 lg:self-start"
    >
      <NavRow
        label="Todas"
        active={activeFolder === undefined}
        onClick={() => onSelectFolder(undefined)}
        count={activeFolder === undefined ? totalCount : undefined}
      />
      <NavRow
        label="Sin carpeta"
        active={activeFolder === "none"}
        onClick={() => onSelectFolder("none")}
      />

      <div className="mt-2.5 mb-0.5 px-2.5 text-[11px] font-semibold uppercase tracking-[0.04em] text-[var(--fg-3)]">
        Carpetas
      </div>

      {(folders ?? []).map((folder) => (
        <FolderRow
          key={folder.id}
          folder={folder}
          active={activeFolder === folder.id}
          onSelect={() => onSelectFolder(folder.id)}
          onRename={() => setRenamingFolder(folder)}
          onDelete={() => setDeletingFolder(folder)}
        />
      ))}

      {folders !== undefined && folders.length === 0 && (
        <p className="px-2.5 py-1 text-[12px] leading-[1.4] text-[var(--fg-3)]">
          Cree carpetas para organizar sus plantillas.
        </p>
      )}

      <Button
        type="button"
        variant="ghost"
        size="sm"
        onClick={() => setCreateOpen(true)}
        className="mt-1.5 justify-start gap-1.5 text-[var(--fg-3)] hover:text-[var(--primary)]"
      >
        <FolderPlus className="size-3.5" />
        Nueva carpeta
      </Button>

      <CreateFolderDialog open={createOpen} onOpenChange={setCreateOpen} />

      {renamingFolder && (
        <RenameFolderDialog
          folder={renamingFolder}
          open={!!renamingFolder}
          onOpenChange={(open) => {
            if (!open) setRenamingFolder(null);
          }}
        />
      )}

      {deletingFolder && (
        <DeleteFolderDialog
          folder={deletingFolder}
          open={!!deletingFolder}
          onOpenChange={(open) => {
            if (!open) setDeletingFolder(null);
          }}
          onDeleted={() => {
            // The deleted folder can no longer be an active filter.
            if (activeFolder === deletingFolder.id) onSelectFolder(undefined);
          }}
        />
      )}
    </nav>
  );
}
