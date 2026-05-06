/**
 * DeactivateUserDialog.tsx
 *
 * Soft-deletes a user account (sets is_active=false). The dialog walks the
 * admin through:
 *   - identity confirmation (avatar / name / email / role)
 *   - optional template reassignment to another active user in the tenant
 *   - confirm-by-typing "DESACTIVAR"
 *
 * If the user owns templates and the admin doesn't pick a reassignment
 * target, the backend responds 409 with a hint. We surface that error in a
 * red banner and force the reassign dropdown into a required state, then
 * the admin can pick a target and resubmit.
 */

import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { CircleAlert, Info, LoaderCircle, UserX } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ROLE_LABELS } from "@/shared/lib/role-labels";

import { useDeactivateUser, type UserResponse } from "../api";

interface DeactivateUserDialogProps {
  user: UserResponse;
  /** Other active users in the tenant (will be filtered to exclude `user`). */
  candidates: UserResponse[];
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}

const CONFIRM_PHRASE = "DESACTIVAR";

function getInitials(email: string): string {
  const local = email.split("@")[0] ?? email;
  const parts = local.split(/[._-]/).filter(Boolean);
  const first = parts[0]?.[0] ?? "?";
  const second = parts[1]?.[0] ?? parts[0]?.[1] ?? "";
  return (first + second).toUpperCase();
}

function rolePillClasses(role: string) {
  if (role === "admin") {
    return "bg-gradient-to-br from-[#004ac6] to-[#2563eb] text-white border-0 rounded-full";
  }
  if (role === "template_creator") {
    return "bg-[var(--bg-accent)] text-[var(--primary)] border-0 rounded-full";
  }
  return "bg-[var(--bg-muted)] text-[var(--fg-2)] border-0 rounded-full";
}

export function DeactivateUserDialog({
  user,
  candidates,
  open: openProp,
  onOpenChange,
}: DeactivateUserDialogProps) {
  const isControlled = openProp !== undefined;
  const [internalOpen, setInternalOpen] = useState(false);
  const open = isControlled ? openProp : internalOpen;
  const setOpen = (v: boolean) => {
    if (isControlled) onOpenChange?.(v);
    else setInternalOpen(v);
  };

  const [confirmText, setConfirmText] = useState("");
  const [reassignTo, setReassignTo] = useState<string>("");
  // Set to true after the backend rejects with 409 (user owns templates).
  // Once true, the reassign select becomes required.
  const [reassignRequired, setReassignRequired] = useState(false);
  const [ownedCount, setOwnedCount] = useState<number | null>(null);

  const deactivateMutation = useDeactivateUser();

  // Reset every piece of local state when the dialog re-opens for a fresh
  // attempt (or when switching to a different user).
  useEffect(() => {
    if (!open) return;
    setConfirmText("");
    setReassignTo("");
    setReassignRequired(false);
    setOwnedCount(null);
  }, [open, user.id]);

  const eligibleCandidates = useMemo(
    () =>
      candidates.filter(
        (c) => c.is_active && c.id !== user.id && c.role !== undefined,
      ),
    [candidates, user.id],
  );

  const phraseOk = confirmText.trim() === CONFIRM_PHRASE;
  const reassignOk = !reassignRequired || reassignTo.length > 0;
  const canSubmit = phraseOk && reassignOk && !deactivateMutation.isPending;

  async function handleSubmit() {
    try {
      await deactivateMutation.mutateAsync({
        id: user.id,
        reassignTo: reassignTo || undefined,
      });
      toast.success(
        reassignTo
          ? "Usuario desactivado y plantillas reasignadas"
          : "Usuario desactivado",
      );
      setOpen(false);
    } catch (err: unknown) {
      const response =
        err && typeof err === "object" && "response" in err
          ? (
              err as {
                response?: { status?: number; data?: { detail?: string } };
              }
            ).response
          : undefined;
      const status = response?.status;
      const detail = response?.data?.detail ?? "";

      if (status === 409) {
        // User has templates and admin didn't pass reassign_to. Extract the
        // count from the backend message if present, force the reassign
        // dropdown into a required state, and stop — the admin retries.
        const match = /tiene (\d+) plantilla/i.exec(detail);
        const count = match ? Number(match[1]) : null;
        setOwnedCount(count);
        setReassignRequired(true);
        toast.error(
          count !== null
            ? `Este usuario tiene ${count} plantilla(s). Seleccioná un destino para reasignarlas.`
            : detail || "Hay que reasignar plantillas antes de desactivar.",
        );
        return;
      }
      if (status === 400) {
        toast.error(detail || "Reasignación inválida");
        return;
      }
      if (status === 404) {
        toast.error(detail || "Usuario destino no encontrado");
        return;
      }
      toast.error(detail || "Error al desactivar usuario");
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-h-[88vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="text-xl font-bold tracking-tight">
            Desactivar usuario
          </DialogTitle>
          <DialogDescription>
            La cuenta queda inactiva y no podrá iniciar sesión. Esta acción es
            reversible — un administrador puede reactivarla más adelante.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4 py-2">
          {/* Identity card */}
          <div className="flex items-center gap-3 rounded-xl bg-[var(--bg-page)] p-3.5 ring-1 ring-[rgba(195,198,215,0.30)]">
            <span className="inline-flex size-10 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-[#004ac6] to-[#2563eb] text-[12px] font-semibold text-white">
              {getInitials(user.email)}
            </span>
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-semibold text-[var(--fg-1)]">
                {user.full_name}
              </div>
              <div className="truncate font-mono text-[11.5px] text-[var(--fg-3)]">
                {user.email}
              </div>
            </div>
            <span
              className={`inline-flex items-center px-2 py-0.5 text-[11px] font-semibold ${rolePillClasses(user.role)}`}
            >
              {ROLE_LABELS[user.role as keyof typeof ROLE_LABELS] ?? user.role}
            </span>
          </div>

          {/* Reassignment block */}
          <div className="grid gap-1.5">
            <Label
              htmlFor="reassign-to"
              className="flex items-center gap-1 text-xs font-semibold uppercase tracking-[0.04em] text-[var(--fg-3)]"
            >
              Reasignar plantillas a
              {reassignRequired && (
                <span className="text-[var(--destructive)]">*</span>
              )}
              {!reassignRequired && (
                <span className="text-[10px] font-normal normal-case tracking-normal text-[var(--fg-3)]">
                  (opcional)
                </span>
              )}
            </Label>

            {eligibleCandidates.length === 0 ? (
              <div className="rounded-lg border border-dashed border-[rgba(195,198,215,0.40)] p-3 text-[12.5px] text-[var(--fg-3)]">
                No hay otros usuarios activos en la organización para reasignar
                plantillas.
              </div>
            ) : (
              <Select
                value={reassignTo}
                onValueChange={(v) => setReassignTo(v ?? "")}
              >
                <SelectTrigger id="reassign-to" className="h-10">
                  <SelectValue placeholder="Seleccionar usuario destino…" />
                </SelectTrigger>
                <SelectContent>
                  {eligibleCandidates.map((c) => (
                    <SelectItem key={c.id} value={c.id}>
                      <span className="font-medium">{c.full_name}</span>
                      <span className="ml-2 font-mono text-[11px] text-[var(--fg-3)]">
                        {c.email}
                      </span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}

            {reassignRequired && ownedCount !== null && (
              <div className="flex items-start gap-2.5 rounded-[10px] bg-[#ffdad6] px-3.5 py-2.5 text-[12.5px] leading-[1.45] text-[#93000a]">
                <CircleAlert className="mt-px size-4 shrink-0 text-[var(--destructive)]" />
                <div className="flex-1">
                  <strong className="font-semibold">
                    Este usuario es propietario de {ownedCount} plantilla
                    {ownedCount === 1 ? "" : "s"}.
                  </strong>{" "}
                  Seleccioná un destino para reasignarlas antes de continuar; sin
                  reasignar quedarían inaccesibles hasta reactivar la cuenta.
                </div>
              </div>
            )}

            {!reassignRequired && (
              <div className="flex items-start gap-2 rounded-[10px] bg-[var(--bg-accent)]/50 px-3.5 py-2.5 text-[12px] leading-[1.45] text-[var(--primary)]">
                <Info className="mt-px size-3.5 shrink-0" />
                <span>
                  Si el usuario tiene plantillas, te las pediremos reasignar
                  antes de desactivar.
                </span>
              </div>
            )}
          </div>

          {/* Confirm by typing */}
          <div className="grid gap-1.5">
            <Label
              htmlFor="confirm-deactivate"
              className="text-xs font-semibold uppercase tracking-[0.04em] text-[var(--fg-3)]"
            >
              Para confirmar, escriba{" "}
              <span className="font-mono text-[var(--destructive)]">
                {CONFIRM_PHRASE}
              </span>
            </Label>
            <Input
              id="confirm-deactivate"
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              placeholder={CONFIRM_PHRASE}
              autoFocus
              autoComplete="off"
            />
          </div>
        </div>

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => setOpen(false)}
          >
            Cancelar
          </Button>
          <Button
            type="button"
            onClick={handleSubmit}
            disabled={!canSubmit}
            className="bg-[var(--destructive)] font-semibold text-white hover:bg-[#93000a]"
          >
            {deactivateMutation.isPending ? (
              <>
                <LoaderCircle className="mr-2 size-4 animate-spin" />
                Desactivando…
              </>
            ) : (
              <>
                <UserX className="mr-2 size-4" />
                Desactivar usuario
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
