import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { CHANGELOG } from "@/shared/version";

interface ChangelogDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * "Novedades" dialog — renders the in-app changelog from the shared
 * version module, one section per version, newest first. Controlled by
 * the caller (login footer, header user menu) so the trigger can live
 * anywhere without duplicating content.
 */
export function ChangelogDialog({ open, onOpenChange }: ChangelogDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[85vh] flex-col gap-0 overflow-hidden p-0 sm:max-w-lg">
        <DialogHeader className="border-b border-[rgba(195,198,215,0.20)] px-6 py-5">
          <DialogTitle className="text-xl font-bold tracking-tight">
            Novedades
          </DialogTitle>
          <DialogDescription>
            Mejoras y cambios de SigDoc, por versión.
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto px-6 py-5">
          <div className="flex flex-col gap-5">
            {CHANGELOG.map((entry, index) => (
              <section
                key={entry.version}
                className={
                  index > 0
                    ? "flex flex-col gap-2.5 border-t border-[rgba(195,198,215,0.20)] pt-5"
                    : "flex flex-col gap-2.5"
                }
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Badge
                    variant={index === 0 ? "default" : "outline"}
                    className={
                      index === 0
                        ? "rounded-full border-0 bg-[var(--bg-accent)] font-mono font-semibold text-[var(--primary)] hover:bg-[var(--bg-accent)]"
                        : "rounded-full border-[rgba(195,198,215,0.40)] font-mono text-[var(--fg-3)]"
                    }
                  >
                    v{entry.version}
                  </Badge>
                  <h3 className="text-sm font-semibold text-[var(--fg-1)]">
                    {entry.title}
                  </h3>
                  {index === 0 && (
                    <Badge className="rounded-full border-0 bg-[#d1fae5] text-[#065f46] hover:bg-[#d1fae5]">
                      <span className="size-1.5 rounded-full bg-[#065f46]" />
                      Actual
                    </Badge>
                  )}
                  {entry.date && (
                    <span className="ml-auto text-[11px] text-[var(--fg-3)]">
                      {entry.date}
                    </span>
                  )}
                </div>

                <ul className="flex flex-col gap-1.5">
                  {entry.items.map((item) => (
                    <li
                      key={item}
                      className="flex items-start gap-2 text-[13px] leading-[1.45] text-[var(--fg-2)]"
                    >
                      <span className="mt-[7px] size-1 shrink-0 rounded-full bg-[var(--fg-4)]" />
                      {item}
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
