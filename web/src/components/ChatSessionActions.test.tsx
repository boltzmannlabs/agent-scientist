// @vitest-environment jsdom
import { act, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "@/i18n";

const mocks = vi.hoisted(() => ({
  deleteSession: vi.fn(),
  getSessionDetail: vi.fn(),
  getSessionExport: vi.fn(),
  updateSession: vi.fn(),
  gatewayConnect: vi.fn(),
  gatewayRequest: vi.fn(),
  gatewayClose: vi.fn(),
}));

vi.mock("@/lib/api", () => ({ api: {
  deleteSession: mocks.deleteSession,
  getSessionDetail: mocks.getSessionDetail,
  getSessionExport: mocks.getSessionExport,
  updateSession: mocks.updateSession,
} }));

vi.mock("@/lib/gatewayClient", () => ({ GatewayClient: class {
  connect = mocks.gatewayConnect;
  request = mocks.gatewayRequest;
  close = mocks.gatewayClose;
} }));

import { ChatSessionActions } from "./ChatSessionActions";
import type { SessionInfo } from "@/lib/api";

const session: SessionInfo = {
  id: "saved-session-1", source: "web", model: "gpt-test", title: "Project notes",
  started_at: 1_700_000_000, ended_at: 1_700_000_100, last_active: 1_700_000_100,
  is_active: false, message_count: 2, tool_call_count: 0, input_tokens: 0,
  output_tokens: 0, preview: "A saved research chat", profile: "profile-a", cwd: "/work/project",
};

let root: Root;
let host: HTMLDivElement;
const onUpdated = vi.fn();
const onRemoved = vi.fn();
const onForked = vi.fn();
const originalCreateObjectURL = Object.getOwnPropertyDescriptor(URL, "createObjectURL");
const originalRevokeObjectURL = Object.getOwnPropertyDescriptor(URL, "revokeObjectURL");

async function render(ui: ReactNode) {
  await act(async () => root.render(<MemoryRouter><I18nProvider>{ui}</I18nProvider></MemoryRouter>));
}

async function clickButton(name: string) {
  const button = Array.from(document.querySelectorAll("button")).find((candidate) =>
    candidate.getAttribute("aria-label") === name || candidate.textContent?.trim() === name,
  );
  if (!button) throw new Error(`Button not found: ${name}`);
  await act(async () => { button.click(); await Promise.resolve(); });
}

async function openMenu() {
  await clickButton("Options for Project notes");
}

beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  mocks.deleteSession.mockReset().mockResolvedValue({ ok: true });
  mocks.getSessionDetail.mockReset().mockResolvedValue(session);
  mocks.getSessionExport.mockReset().mockResolvedValue({ ...session, messages: [
    { role: "user", content: "Review this structure" },
    { role: "assistant", content: "I will compare the evidence." },
  ] });
  mocks.updateSession.mockReset().mockResolvedValue({ ok: true, title: "Project notes", pinned: true, archived: false });
  mocks.gatewayConnect.mockReset().mockResolvedValue(undefined);
  mocks.gatewayRequest.mockReset().mockResolvedValue({ stored_session_id: "forked-session-1" });
  mocks.gatewayClose.mockReset();
  onUpdated.mockReset(); onRemoved.mockReset(); onForked.mockReset();
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
});

afterEach(async () => {
  vi.useRealTimers();
  await act(async () => root.unmount());
  host.remove();
  vi.restoreAllMocks();
  if (originalCreateObjectURL) Object.defineProperty(URL, "createObjectURL", originalCreateObjectURL);
  else Reflect.deleteProperty(URL, "createObjectURL");
  if (originalRevokeObjectURL) Object.defineProperty(URL, "revokeObjectURL", originalRevokeObjectURL);
  else Reflect.deleteProperty(URL, "revokeObjectURL");
});

describe("saved chat actions", () => {
  it("pins and archives through the owning profile, removing archived chats from active history", async () => {
    await render(<ChatSessionActions session={session} onUpdated={onUpdated} onRemoved={onRemoved} onForked={onForked} />);
    await openMenu();
    await clickButton("Pin conversation");
    expect(mocks.updateSession).toHaveBeenCalledWith(session.id, { pinned: true }, "profile-a");
    expect(onUpdated).toHaveBeenCalledWith({ pinned: true });

    await openMenu();
    await clickButton("Archive");
    expect(mocks.updateSession).toHaveBeenCalledWith(session.id, { archived: true, pinned: false }, "profile-a");
    expect(onRemoved).toHaveBeenCalledOnce();
  });

  it("requires confirmation before deletion and renames using the session API", async () => {
    await render(<ChatSessionActions session={session} onUpdated={onUpdated} onRemoved={onRemoved} onForked={onForked} />);
    await openMenu();
    await clickButton("Rename");
    const input = document.querySelector<HTMLInputElement>('input[aria-label="Conversation title"]')!;
    await act(async () => {
      const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
      setter.call(input, "Antibody evidence review");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    mocks.updateSession.mockResolvedValueOnce({ ok: true, title: "Antibody evidence review" });
    await clickButton("Save title");
    expect(mocks.updateSession).toHaveBeenCalledWith(session.id, { title: "Antibody evidence review" }, "profile-a");
    expect(onUpdated).toHaveBeenCalledWith({ title: "Antibody evidence review" });

    await openMenu();
    await clickButton("Delete");
    expect(mocks.deleteSession).not.toHaveBeenCalled();
    await clickButton("Delete conversation");
    expect(mocks.deleteSession).toHaveBeenCalledWith(session.id, "profile-a");
    expect(onRemoved).toHaveBeenCalledOnce();
  });

  it("creates a server-side branch from the saved transcript and starts sharing only after consent", async () => {
    await render(<ChatSessionActions session={session} onUpdated={onUpdated} onRemoved={onRemoved} onForked={onForked} />);
    await openMenu();
    await clickButton("Fork conversation · Essential");
    expect(mocks.getSessionDetail).toHaveBeenCalledWith(session.id, "profile-a");
    expect(mocks.gatewayRequest).toHaveBeenCalledWith("session.branch_stored", {
      parent_session_id: session.id, source: "web", cols: 96, profile: "profile-a", cwd: "/work/project",
    });
    expect(onForked).toHaveBeenCalledWith("forked-session-1");
    expect(mocks.gatewayClose).toHaveBeenCalledOnce();

    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
    await openMenu();
    await clickButton("Share transcript…");
    expect(mocks.getSessionExport).not.toHaveBeenCalled();
    await clickButton("Share transcript");
    expect(mocks.getSessionExport).toHaveBeenCalledWith(session.id, "profile-a");
    expect(writeText).toHaveBeenCalledOnce();
    expect(writeText.mock.calls[0][0]).toContain("Review this structure");
    expect(writeText.mock.calls[0][0]).toContain("resume=saved-session-1");
  });

  it("downloads real Markdown and JSON files and sends PDF through the browser print flow", async () => {
    const files: string[] = [];
    Object.defineProperty(URL, "createObjectURL", { configurable: true, value: vi.fn(() => "blob:export") });
    Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: vi.fn() });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      files.push(this.download);
    });
    await render(<ChatSessionActions session={session} onUpdated={onUpdated} onRemoved={onRemoved} onForked={onForked} />);
    await openMenu();
    await clickButton("Download");
    expect(document.querySelector('[aria-label="Download format"]')?.textContent).toContain("Markdown");
    await clickButton("Markdown");
    expect(files).toContain("agent-scientist-Project-notes.md");

    await openMenu();
    await clickButton("Download");
    await clickButton("JSON");
    expect(files).toContain("agent-scientist-Project-notes.json");

    vi.useFakeTimers();
    const printDocument = document.implementation.createHTMLDocument();
    const printWindow = { document: printDocument, focus: vi.fn(), print: vi.fn() } as unknown as Window;
    vi.spyOn(window, "open").mockReturnValue(printWindow);
    await openMenu();
    await clickButton("Download");
    await clickButton("PDF · print or save");
    expect(printDocument.body.textContent).toContain("Review this structure");
    expect(document.body.textContent).toContain("Choose Save as PDF");
    await act(async () => { vi.advanceTimersByTime(400); });
    expect(printWindow.print).toHaveBeenCalledOnce();
    vi.useRealTimers();
  });
});
