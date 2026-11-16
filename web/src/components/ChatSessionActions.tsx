import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  Archive,
  Braces,
  Check,
  Download,
  GitBranch,
  MoreHorizontal,
  Pin,
  Share2,
  Trash2,
  Pencil,
} from "lucide-react";

import { Button } from "@sci/ui/ui/components/button";
import { ConfirmDialog } from "@sci/ui/ui/components/confirm-dialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@sci/ui/ui/components/dialog";
import { Input } from "@sci/ui/ui/components/input";
import { api, type SessionInfo } from "@/lib/api";
import { GatewayClient } from "@/lib/gatewayClient";

interface ChatSessionActionsProps {
  session: SessionInfo;
  profile?: string;
  onUpdated: (updates: Partial<SessionInfo>) => void;
  onRemoved: () => void;
  onForked: (sessionId: string) => void;
}

type DownloadFormat = "md" | "pdf" | "json";

function sessionTitle(session: SessionInfo): string {
  return session.title?.trim() && session.title !== "Untitled"
    ? session.title
    : session.preview?.trim() || "Research conversation";
}

function filenamePart(value: string): string {
  const clean = Array.from(value.normalize("NFKD"), char =>
    char.charCodeAt(0) < 32 ? "-" : char,
  ).join("")
    .replace(/[<>:"/\\|?*]/g, "-")
    .replace(/[. ]+$/g, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .slice(0, 72);
  return clean || "research-conversation";
}

function messageText(content: unknown): string {
  if (typeof content === "string") return content.replace(/data:image\/[\w.+-]+;base64,[A-Za-z0-9+/=]+/g, "[image attachment]");
  if (content == null) return "";
  if (Array.isArray(content)) {
    return content.map((part) => {
      if (typeof part === "string") return part;
      if (!part || typeof part !== "object") return "";
      const item = part as Record<string, unknown>;
      if (typeof item.text === "string") return item.text;
      if (item.type === "image" || item.type === "image_url") return "[image attachment]";
      return "";
    }).filter(Boolean).join("\n");
  }
  return JSON.stringify(content, null, 2);
}

function transcriptMarkdown(session: SessionInfo, exported: Record<string, unknown>): string {
  const title = sessionTitle(session);
  const rows = Array.isArray(exported.messages) ? exported.messages : [];
  const messages = rows.map((raw) => {
    if (!raw || typeof raw !== "object") return "";
    const message = raw as Record<string, unknown>;
    const role = String(message.role || "message");
    const heading = role === "user" ? "You" : role === "assistant" ? "Agent Scientist" :
      role === "tool" ? `Tool result${message.tool_name ? ` · ${String(message.tool_name)}` : ""}` : role;
    const body = messageText(message.content);
    const calls = Array.isArray(message.tool_calls) ? message.tool_calls : [];
    const callText = calls.map((rawCall) => {
      if (!rawCall || typeof rawCall !== "object") return "";
      const call = rawCall as Record<string, unknown>;
      const fn = call.function && typeof call.function === "object"
        ? call.function as Record<string, unknown>
        : {};
      const name = String(fn.name || "tool");
      let args = String(fn.arguments || "{}");
      try { args = JSON.stringify(JSON.parse(args), null, 2); } catch { /* Keep the recorded arguments intact. */ }
      return `**Tool call: ${name}**\n\n\`\`\`json\n${args}\n\`\`\``;
    }).filter(Boolean).join("\n\n");
    return body || callText ? `## ${heading}\n\n${[body, callText].filter(Boolean).join("\n\n")}` : "";
  }).filter(Boolean);
  const started = new Date(session.started_at * 1000).toISOString();
  return `# ${title}\n\nExported from Agent Scientist · ${started}\n\n${messages.join("\n\n---\n\n")}\n`;
}

function downloadText(text: string, mime: string, filename: string): void {
  const url = URL.createObjectURL(new Blob([text], { type: mime }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function copyText(text: string): Promise<void> {
  if (navigator.clipboard?.writeText) return navigator.clipboard.writeText(text);
  return new Promise((resolve, reject) => {
    const field = document.createElement("textarea");
    field.value = text;
    field.setAttribute("readonly", "");
    field.style.position = "fixed";
    field.style.opacity = "0";
    document.body.append(field);
    field.select();
    const copied = document.execCommand("copy");
    field.remove();
    if (copied) resolve();
    else reject(new Error("Clipboard access is unavailable. Use Download → Markdown instead."));
  });
}

function writePrintView(target: Window, title: string, markdown: string): void {
  const doc = target.document;
  doc.open();
  doc.write("<!doctype html><html><head><meta charset=\"utf-8\"><title></title></head><body></body></html>");
  doc.close();
  doc.title = title;
  const style = doc.createElement("style");
  style.textContent = "body{font:14px/1.6 system-ui,sans-serif;color:#171717;max-width:850px;margin:48px auto;padding:0 28px}h1{font-size:26px;border-bottom:1px solid #bbb;padding-bottom:12px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit}@page{margin:18mm} @media print{body{margin:0;max-width:none;padding:0}}";
  const heading = doc.createElement("h1");
  heading.textContent = title;
  const body = doc.createElement("pre");
  body.textContent = markdown.replace(/^# .*\n+/, "");
  doc.head.append(style);
  doc.body.replaceChildren(heading, body);
  window.setTimeout(() => { target.focus(); target.print(); }, 350);
}

export function ChatSessionActions({
  session,
  profile,
  onUpdated,
  onRemoved,
  onForked,
}: ChatSessionActionsProps) {
  const owner = session.profile ?? profile;
  const [menuOpen, setMenuOpen] = useState(false);
  const [downloadOpen, setDownloadOpen] = useState(false);
  const [renameOpen, setRenameOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);
  const [renameValue, setRenameValue] = useState(session.title || "");
  const [busy, setBusy] = useState("");
  const [status, setStatus] = useState("");
  const [menuPosition, setMenuPosition] = useState({ top: 8, right: 8 });
  const menuRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    const closeOutside = (event: PointerEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) {
        setMenuOpen(false);
        setDownloadOpen(false);
      }
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setMenuOpen(false);
        setDownloadOpen(false);
        triggerRef.current?.focus();
      } else if (event.key === "ArrowDown" || event.key === "ArrowUp" || event.key === "Home" || event.key === "End") {
        const items = Array.from(menuRef.current?.querySelectorAll<HTMLButtonElement>(".chat-session-actions-menu [role=menuitem]:not(:disabled)") ?? []);
        if (!items.length) return;
        event.preventDefault();
        const current = items.indexOf(document.activeElement as HTMLButtonElement);
        const next = event.key === "Home" ? 0 : event.key === "End" ? items.length - 1 :
          event.key === "ArrowDown" ? (current + 1 + items.length) % items.length : (current - 1 + items.length) % items.length;
        items[next]?.focus();
      }
    };
    document.addEventListener("pointerdown", closeOutside);
    document.addEventListener("keydown", closeOnEscape);
    menuRef.current?.querySelector<HTMLButtonElement>("[role=menuitem]")?.focus();
    return () => {
      document.removeEventListener("pointerdown", closeOutside);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [menuOpen]);

  async function update(patch: { title?: string; pinned?: boolean; archived?: boolean }) {
    setBusy("update");
    setStatus("");
    try {
      const result = await api.updateSession(session.id, patch, owner);
      if (patch.title !== undefined) onUpdated({ title: result.title });
      if (patch.pinned !== undefined) onUpdated({ pinned: result.pinned ?? patch.pinned });
      if (patch.archived !== undefined) onRemoved();
      setMenuOpen(false);
      setStatus(patch.archived ? "Conversation archived." : patch.pinned !== undefined
        ? (patch.pinned ? "Conversation pinned." : "Conversation unpinned.")
        : "Conversation renamed.");
      if (patch.title !== undefined) setRenameOpen(false);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Could not update this conversation.");
    } finally {
      setBusy("");
    }
  }

  async function forkConversation() {
    setBusy("fork");
    setStatus("Creating a branch from this saved conversation…");
    setMenuOpen(false);
    let gateway: GatewayClient | null = null;
    try {
      const detail = await api.getSessionDetail(session.id, owner);
      gateway = new GatewayClient();
      await gateway.connect();
      const result = await gateway.request<{ stored_session_id: string }>("session.branch_stored", {
        parent_session_id: session.id,
        source: "web",
        cols: 96,
        ...(owner ? { profile: owner } : {}),
        ...(detail.cwd ? { cwd: detail.cwd } : {}),
      });
      onForked(result.stored_session_id);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Could not fork this conversation.");
    } finally {
      gateway?.close();
      setBusy("");
    }
  }

  async function fetchExport() {
    const exported = await api.getSessionExport(session.id, owner) as unknown as Record<string, unknown>;
    return { exported, markdown: transcriptMarkdown(session, exported) };
  }

  async function download(format: DownloadFormat) {
    setBusy(`download-${format}`);
    setStatus(`Preparing ${format.toUpperCase()} export…`);
    setMenuOpen(false);
    setDownloadOpen(false);
    let printWindow: Window | null = null;
    if (format === "pdf") {
      printWindow = window.open("about:blank", "_blank");
      if (!printWindow) {
        setBusy("");
        setStatus("Allow pop-ups to open the print dialog and save as PDF.");
        return;
      }
    }
    try {
      const { exported, markdown } = await fetchExport();
      const filename = `agent-scientist-${filenamePart(sessionTitle(session))}`;
      if (format === "md") downloadText(markdown, "text/markdown;charset=utf-8", `${filename}.md`);
      else if (format === "json") downloadText(JSON.stringify(exported, null, 2), "application/json;charset=utf-8", `${filename}.json`);
      else if (printWindow) writePrintView(printWindow, sessionTitle(session), markdown);
      setStatus(format === "pdf" ? "Print dialog opened. Choose Save as PDF to download it." : `Conversation downloaded as ${format.toUpperCase()}.`);
    } catch (error) {
      printWindow?.close();
      setStatus(error instanceof Error ? error.message : "Could not export this conversation.");
    } finally {
      setBusy("");
    }
  }

  async function shareConversation() {
    setBusy("share");
    setShareOpen(false);
    setStatus("Preparing the transcript…");
    try {
      const { markdown } = await fetchExport();
      const link = new URL(window.location.href);
      link.searchParams.set("resume", session.id);
      if (owner) link.searchParams.set("profile", owner);
      const shareText = `${markdown}\n\nOpen this conversation in Agent Scientist: ${link.href}`;
      if (navigator.share) {
        try {
          await navigator.share({ title: sessionTitle(session), text: shareText, url: link.href });
          setStatus("Conversation shared.");
          return;
        } catch (error) {
          if (error instanceof Error && error.name === "AbortError") {
            setStatus("Sharing cancelled.");
            return;
          }
        }
      }
      await copyText(shareText);
      setStatus("Transcript and conversation link copied. The link requires access to this Sci dashboard.");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Could not prepare this conversation for sharing.");
    } finally {
      setBusy("");
    }
  }

  async function confirmDelete() {
    setBusy("delete");
    setStatus("");
    try {
      await api.deleteSession(session.id, owner);
      setDeleteOpen(false);
      onRemoved();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Could not delete this conversation.");
    } finally {
      setBusy("");
    }
  }

  function openRename() {
    setRenameValue(session.title && session.title !== "Untitled" ? session.title : "");
    setMenuOpen(false);
    setRenameOpen(true);
  }

  const item = (icon: ReactNode, label: string, onClick: () => void, disabled = false, description?: string) => (
    <button className="chat-session-action-item" type="button" role="menuitem" aria-label={label} onClick={onClick} disabled={disabled || Boolean(busy)} title={description}>
      {icon}<span>{label}</span>
    </button>
  );

  return (
    <div className="chat-session-actions" ref={menuRef}>
      <button
        ref={triggerRef}
        type="button"
        className="chat-session-actions-trigger"
        aria-label={`Options for ${sessionTitle(session)}`}
        title="Conversation options"
        aria-haspopup="menu"
        aria-expanded={menuOpen}
        onClick={(event) => {
          event.stopPropagation();
          if (!menuOpen) {
            const rect = event.currentTarget.getBoundingClientRect();
            setMenuPosition({
              top: Math.max(8, Math.min(rect.bottom + 3, window.innerHeight - 360)),
              right: Math.max(8, window.innerWidth - rect.right),
            });
          }
          setMenuOpen((open) => !open);
        }}
      >
        <MoreHorizontal size={17} />
      </button>
      {menuOpen && (
        <div className="chat-session-actions-menu" style={menuPosition} role="menu" aria-label={`Options for ${sessionTitle(session)}`}>
          {item(<Pencil />, "Rename", openRename, false, "Change the conversation title.")}
          {item(<GitBranch />, "Fork conversation · Essential", () => void forkConversation(), false, "Create a new conversation from this point while preserving the original.")}
          {item(<Pin />, session.pinned ? "Unpin conversation" : "Pin conversation", () => void update({ pinned: !session.pinned }), false, "Keep this research conversation at the top of history.")}
          {item(<Archive />, "Archive", () => void update({ archived: true, pinned: false }), false, "Hide completed research from active history without deleting it.")}
          <div className="chat-session-action-group">
            {item(<Download />, "Download", () => setDownloadOpen((open) => !open), false, "Export the conversation as Markdown, PDF, or JSON.")}
            {downloadOpen && <div className="chat-session-download-menu" role="group" aria-label="Download format">
              {item(<span className="chat-session-format-icon">M</span>, "Markdown", () => void download("md"))}
              {item(<span className="chat-session-format-icon">P</span>, "PDF · print or save", () => void download("pdf"))}
              {item(<Braces />, "JSON", () => void download("json"))}
            </div>}
          </div>
          {item(<Share2 />, "Share transcript…", () => { setMenuOpen(false); setShareOpen(true); }, false, "Share through your device or copy the transcript and dashboard link.")}
          {item(<Trash2 />, "Delete", () => { setMenuOpen(false); setDeleteOpen(true); }, false, "Permanently delete this conversation after confirmation.")}
        </div>
      )}
      {status && <div className="chat-session-action-status" role="status">{status}</div>}

      <Dialog open={renameOpen} onOpenChange={(open) => { if (!busy) setRenameOpen(open); }}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Rename conversation</DialogTitle>
            <DialogDescription>Change the title shown in your chat history.</DialogDescription>
          </DialogHeader>
          <Input
            autoFocus
            aria-label="Conversation title"
            value={renameValue}
            maxLength={200}
            onChange={(event) => setRenameValue(event.target.value)}
            onKeyDown={(event) => { if (event.key === "Enter") void update({ title: renameValue.trim() }); }}
            placeholder="Conversation title"
            disabled={Boolean(busy)}
          />
          {status && <p className="text-xs text-destructive" role="alert">{status}</p>}
          <DialogFooter>
            <Button outlined disabled={Boolean(busy)} onClick={() => setRenameOpen(false)}>Cancel</Button>
            <Button disabled={Boolean(busy) || !renameValue.trim()} prefix={busy === "update" ? undefined : <Check />} onClick={() => void update({ title: renameValue.trim() })}>
              {busy === "update" ? "Saving…" : "Save title"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={deleteOpen}
        title="Delete conversation permanently?"
        description={status || "This permanently deletes the saved conversation and its messages. This cannot be undone. Active conversations may need to be closed before deletion."}
        destructive
        confirmLabel={busy === "delete" ? "Deleting…" : "Delete conversation"}
        loading={busy === "delete"}
        onCancel={() => setDeleteOpen(false)}
        onConfirm={() => void confirmDelete()}
      />
      <ConfirmDialog
        open={shareOpen}
        title="Share this conversation?"
        description="The full transcript and a link to this Sci dashboard will be sent to your device’s share sheet or copied to your clipboard. Review it first and share only with people allowed to see its contents. No public link is created."
        confirmLabel={busy === "share" ? "Preparing…" : "Share transcript"}
        loading={busy === "share"}
        onCancel={() => setShareOpen(false)}
        onConfirm={() => void shareConversation()}
      />
    </div>
  );
}
