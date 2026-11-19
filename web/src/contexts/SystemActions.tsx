import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { ActionStatusResponse } from "@/lib/api";
import { Toast } from "@sci/ui/ui/components/toast";
import { sharedGatewayProfiles, sharedGatewayRestartedMessage } from "@/lib/shared-gateway";
import { useI18n } from "@/i18n";
import {
  SystemActionsContext,
  type SystemAction,
} from "./system-actions-context";

const ACTION_NAMES: Record<SystemAction, string> = {
  restart: "gateway-restart",
  update: "sci-update",
};

interface ActionAttempt { action: SystemAction; generation: number; actionId?: string }

const PENDING_UPDATE_KEY = "sci.pendingUpdate";

function restoreUpdate(): ActionAttempt | null {
  try {
    const saved = JSON.parse(sessionStorage.getItem(PENDING_UPDATE_KEY) ?? "null");
    if (saved?.action === "update" && (!saved.actionId || typeof saved.actionId === "string")) {
      return { action: "update", generation: 0, actionId: saved.actionId };
    }
  } catch {
    // Browser privacy settings can disable storage; in-page monitoring still works.
  }
  return null;
}

function rememberUpdate(attempt: ActionAttempt | null): void {
  try {
    if (attempt?.action === "update") {
      sessionStorage.setItem(PENDING_UPDATE_KEY, JSON.stringify({ action: "update", actionId: attempt.actionId }));
    } else {
      sessionStorage.removeItem(PENDING_UPDATE_KEY);
    }
  } catch {
    // A blocked storage API must not prevent an update or its status polling.
  }
}

export function SystemActionsProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [pendingAction, setPendingAction] = useState<SystemAction | null>(null);
  const [attempt, setAttempt] = useState<ActionAttempt | null>(restoreUpdate);
  const activeAction = attempt?.action ?? null;
  const generation = useRef(0);
  const submitting = useRef(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [actionStatus, setActionStatus] = useState<ActionStatusResponse | null>(
    null,
  );
  const [toast, setToast] = useState<ToastState | null>(null);
  const { t } = useI18n();

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(timer);
  }, [toast]);

  useEffect(() => {
    if (!attempt) return;
    const name = ACTION_NAMES[attempt.action];
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let request: AbortController | undefined;
    let failures = 0;
    const current = () => !cancelled && generation.current === attempt.generation;

    const poll = async () => {
      try {
        request = new AbortController();
        const timeout = setTimeout(() => request?.abort(), 10000);
        let resp: ActionStatusResponse;
        try { resp = await api.getActionStatus(name, 200, { signal: request.signal }); }
        finally { clearTimeout(timeout); }
        if (!current()) return;
        failures = 0;
        if (attempt.actionId && resp.action_id && attempt.actionId !== resp.action_id) {
          setStatusMessage("Checking update result…");
          timer = setTimeout(poll, 1500);
          return;
        }
        if (!resp.running && resp.exit_code === null) {
          setStatusMessage("Checking update result…");
          timer = setTimeout(poll, 1500);
          return;
        }
        setStatusMessage(null);
        setActionStatus(resp);
        if (!resp.running) {
          rememberUpdate(null);
          const partial = resp.receipt?.outcome === "partial";
          const ok = resp.exit_code === 0 && !partial && resp.receipt?.outcome !== "failed";
          // A restart of the shared multiplexer reconnected every bot on the device: name the count.
          const shared =
            ok && attempt.action === "restart"
              ? sharedGatewayProfiles(await api.getStatus().catch(() => null))
              : null;
          if (!current()) return;
          setToast({
            type: ok ? "success" : "error",
            message: partial ? "Update installed, but some steps need attention. See the update log." : ok
              ? shared
                ? sharedGatewayRestartedMessage(shared.length)
                : t.status.actionFinished
              : `${t.status.actionFailed} (exit ${resp.exit_code ?? "?"})`,
          });
          return;
        }
      } catch {
        if (!current()) return;
        failures++;
        setStatusMessage(failures < 10 ? "Reconnecting…" : "Dashboard unavailable");
        if (failures === 10) setToast({ type: "error", message: "The dashboard is unreachable. The update outcome is unknown. Relaunch sci dashboard on its previous port, then reload; the saved update result will be checked." });
      }
      if (current()) timer = setTimeout(poll, 1500);
    };

    poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
      request?.abort();
    };
  }, [attempt, t.status.actionFinished, t.status.actionFailed]);

  const runAction = useCallback(
    async (action: SystemAction) => {
      if (submitting.current) return;
      submitting.current = true;
      const token = ++generation.current;
      rememberUpdate(null);
      setAttempt(null);
      setPendingAction(action);
      setActionStatus(null);
      setStatusMessage(null);
      try {
        if (action === "restart") {
          await api.restartGateway();
          if (generation.current === token) setAttempt({ action, generation: token });
        } else {
          const resp = await api.updateSci();
          if (generation.current !== token) return;
          // Some installs cannot apply updates from inside the dashboard. The
          // endpoint returns a structured {ok:false, message, update_command}
          // envelope instead of spawning the action; surface that guidance
          // rather than polling a synthetic failed action.
          if (!resp.ok) {
            const cmd = resp.update_command ? `  ${resp.update_command}` : "";
            setToast({
              type: "success",
              message:
                (resp.message ??
                  "Updates don't apply from this dashboard.") +
                cmd,
            });
            return;
          }
          const next = { action, generation: token, actionId: resp.action_id };
          rememberUpdate(next);
          setAttempt(next);
        }
      } catch (err) {
        const detail = err instanceof Error ? err.message : String(err);
        setToast({
          type: "error",
          message: `${t.status.actionFailed}: ${detail}`,
        });
      } finally {
        submitting.current = false;
        setPendingAction(null);
      }
    },
    [t.status.actionFailed],
  );

  const dismissLog = useCallback(() => {
    generation.current++;
    rememberUpdate(null);
    setAttempt(null);
    setActionStatus(null);
    setStatusMessage(null);
  }, []);

  const isRunning = activeAction !== null && actionStatus?.running !== false;
  const isBusy = pendingAction !== null || isRunning;

  return (
    <SystemActionsContext.Provider
      value={{
        actionStatus,
        activeAction,
        dismissLog,
        isBusy,
        isRunning,
        pendingAction,
        statusMessage,
        runAction,
      }}
    >
      {children}
      <Toast toast={toast} />
    </SystemActionsContext.Provider>
  );
}

interface ToastState {
  message: string;
  type: "success" | "error";
}
