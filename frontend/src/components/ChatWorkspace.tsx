import {
  Bot,
  CheckCircle2,
  Code2,
  Copy,
  FolderSync,
  Paperclip,
  RefreshCw,
  Send,
  TerminalSquare,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";

import type { CommandCenterOverview, CommandReference, SessionAttachment, SessionMessage } from "../types/api";

const FALLBACK_COMMANDS: CommandReference[] = [
  {
    command: "/mission <task>",
    description: "Run the multi-agent agency loop.",
    web_available: true,
    web_label: "Run mission",
  },
  {
    command: "/skills",
    description: "Show loaded tools grouped by source.",
    web_available: true,
    web_label: "Command center",
  },
  {
    command: "/memory",
    description: "Show durable memory facts.",
    web_available: true,
    web_label: "Command center",
  },
  {
    command: "/mcp",
    description: "Show MCP server status and discovered tools.",
    web_available: true,
    web_label: "Command center",
  },
  {
    command: "/mcp refresh",
    description: "Refresh MCP discovery and reuse cached inventory if a server refresh fails.",
    web_available: true,
    web_label: "Refresh MCP discovery",
  },
  {
    command: "/prepare",
    description: "Prepare sandbox image and local model assets.",
    web_available: true,
    web_label: "Prepare runtime",
  },
  {
    command: "/session",
    description: "Create a fresh session id.",
    web_available: true,
    web_label: "New session",
  },
  {
    command: "/reload",
    description: "Reload skills and refresh the search index.",
    web_available: true,
    web_label: "Reload tools",
  },
  {
    command: "/verify",
    description: "Run skill integrity checks and runtime verification.",
    web_available: true,
    web_label: "Verify runtime",
  },
  {
    command: "/help",
    description: "Show the slash command reference.",
    web_available: true,
    web_label: "Command map",
  },
  {
    command: "/quit | /exit | /q",
    description: "Exit the terminal interface.",
    web_available: false,
    web_label: null,
  },
];

type ParsedSlashCommand =
  | { kind: "mission"; task: string }
  | { kind: "show-help" }
  | { kind: "show-skills" }
  | { kind: "show-memory" }
  | { kind: "show-mcp" }
  | { kind: "refresh-mcp" }
  | { kind: "prepare" }
  | { kind: "new-session" }
  | { kind: "reload" }
  | { kind: "verify" }
  | { kind: "unsupported"; message: string };

function formatBytes(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }

  const kilobytes = bytes / 1024;
  if (kilobytes < 1024) {
    return `${kilobytes.toFixed(kilobytes >= 100 ? 0 : 1)} KB`;
  }

  return `${(kilobytes / 1024).toFixed(1)} MB`;
}

function parseSlashCommand(input: string): ParsedSlashCommand | null {
  const trimmed = input.trim();
  if (!trimmed.startsWith("/")) {
    return null;
  }

  const normalized = trimmed.replace(/\s+/g, " ").toLowerCase();
  if (normalized === "/help") {
    return { kind: "show-help" };
  }

  if (normalized === "/skills") {
    return { kind: "show-skills" };
  }

  if (normalized === "/memory") {
    return { kind: "show-memory" };
  }

  if (normalized === "/mcp") {
    return { kind: "show-mcp" };
  }

  if (normalized === "/mcp refresh") {
    return { kind: "refresh-mcp" };
  }

  if (normalized === "/prepare") {
    return { kind: "prepare" };
  }

  if (normalized === "/session") {
    return { kind: "new-session" };
  }

  if (normalized === "/reload") {
    return { kind: "reload" };
  }

  if (normalized === "/verify") {
    return { kind: "verify" };
  }

  if (normalized === "/quit" || normalized === "/exit" || normalized === "/q") {
    return { kind: "unsupported", message: "Terminal exit commands are only available in the CLI." };
  }

  if (normalized === "/mission") {
    return { kind: "unsupported", message: "/mission requires a task after the command." };
  }

  if (normalized.startsWith("/mission ")) {
    return { kind: "mission", task: trimmed.slice(8).trim() };
  }

  return { kind: "unsupported", message: `${trimmed} is not mapped to a browser slash command yet.` };
}

function commandQuery(draft: string): string {
  const trimmed = draft.trimStart();
  return trimmed.startsWith("/") ? trimmed.toLowerCase() : "";
}

function commandExecutionLabel(command: CommandReference): string {
  const normalized = command.command.trim().toLowerCase();
  if (normalized === "/help" || normalized === "/skills" || normalized === "/memory" || normalized === "/mcp") {
    return "Chat reply";
  }

  return command.web_label ?? "Web";
}

function formatCommandList(commands: CommandReference[]): string {
  const webCommands = commands.filter((command) => command.web_available);
  const terminalOnlyCommands = commands.filter((command) => !command.web_available);
  const lines = ["Browser slash commands:"];

  for (const command of webCommands) {
    lines.push(`- ${command.command}: ${command.description}`);
  }

  if (terminalOnlyCommands.length > 0) {
    lines.push("");
    lines.push("Terminal-only commands:");
    for (const command of terminalOnlyCommands) {
      lines.push(`- ${command.command}: ${command.description}`);
    }
  }

  return lines.join("\n");
}

function formatToolInventorySummary(overview: CommandCenterOverview | null): string {
  if (overview === null) {
    return "Tool inventory is still loading. Try /skills again in a moment.";
  }

  if (overview.tools.length === 0) {
    return "No tools are currently visible to the browser runtime.";
  }

  const grouped = new Map<string, string[]>();
  for (const tool of overview.tools) {
    const key = tool.source_label || tool.source;
    const existing = grouped.get(key) ?? [];
    existing.push(tool.name);
    grouped.set(key, existing);
  }

  const lines = [`Visible tools: ${overview.tools.length}`];
  for (const [label, names] of Array.from(grouped.entries()).sort((left, right) => left[0].localeCompare(right[0]))) {
    const preview = names.slice(0, 6).join(", ");
    const suffix = names.length > 6 ? `, +${names.length - 6} more` : "";
    lines.push(`- ${label} (${names.length}): ${preview}${suffix}`);
  }
  return lines.join("\n");
}

function formatDurableMemorySummary(overview: CommandCenterOverview | null): string {
  if (overview === null) {
    return "Durable memory is still loading. Try /memory again in a moment.";
  }

  const facts = overview.memory.facts;
  if (facts.length === 0) {
    return "No durable memory facts are stored yet.";
  }

  const lines = ["Durable memory facts:"];
  for (const fact of facts.slice(0, 12)) {
    lines.push(fact);
  }
  if (facts.length > 12) {
    lines.push(`- ... and ${facts.length - 12} more fact(s).`);
  }
  return lines.join("\n");
}

function formatMcpSummary(overview: CommandCenterOverview | null): string {
  if (overview === null) {
    return "MCP status is still loading. Try /mcp again in a moment.";
  }

  const lines = [overview.mcp.message];
  if (overview.mcp.servers.length === 0) {
    lines.push("No MCP servers are configured for the current browser runtime.");
    return lines.join("\n");
  }

  lines.push("");
  lines.push("Servers:");
  for (const server of overview.mcp.servers) {
    const discoveredCount = server.discovered_tools.length;
    let serverLine = `- ${server.name}: ${server.state}, ${discoveredCount} discovered tool${discoveredCount === 1 ? "" : "s"}`;
    if (server.last_error) {
      serverLine += `, last error: ${server.last_error}`;
    }
    lines.push(serverLine);
  }

  return lines.join("\n");
}

interface ChatWorkspaceProps {
  sessionId: string | null;
  messages: SessionMessage[];
  attachments: SessionAttachment[];
  commandCenterOverview: CommandCenterOverview | null;
  error: string | null;
  isBootstrapping: boolean;
  isSending: boolean;
  isRunningMission: boolean;
  isUploadingAttachments: boolean;
  deletingAttachmentId: string | null;
  commands: CommandReference[];
  onNewSession: () => Promise<void>;
  onSendMessage: (message: string) => Promise<void>;
  onRunMission: (message: string) => Promise<void>;
  onUploadAttachments: (files: File[]) => Promise<void>;
  onDeleteAttachment: (attachmentId: string) => Promise<void>;
  onRefreshMcp: () => Promise<void>;
  onReloadTools: () => Promise<void>;
  onPrepareRuntime: () => Promise<void>;
  onVerifyRuntime: () => Promise<void>;
}

/**
 * Design reference: frontend/design.md -> Overview, Colors.
 */
export function ChatWorkspace({
  sessionId,
  messages,
  attachments,
  commandCenterOverview,
  error,
  isBootstrapping,
  isSending,
  isRunningMission,
  isUploadingAttachments,
  deletingAttachmentId,
  commands,
  onNewSession,
  onSendMessage,
  onRunMission,
  onUploadAttachments,
  onDeleteAttachment,
  onRefreshMcp,
  onReloadTools,
  onPrepareRuntime,
  onVerifyRuntime,
}: ChatWorkspaceProps) {
  const [draft, setDraft] = useState("");
  const [localCommandMessages, setLocalCommandMessages] = useState<SessionMessage[]>([]);
  const [composerError, setComposerError] = useState<string | null>(null);
  const [composerNotice, setComposerNotice] = useState<string | null>(null);
  const [isSlashMenuOpen, setIsSlashMenuOpen] = useState(false);
  const [isExecutingCommand, setIsExecutingCommand] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const isAssistantStreaming = isSending && messages[messages.length - 1]?.role === "assistant";
  const availableCommands = commands.length > 0 ? commands : FALLBACK_COMMANDS;
  const slashQuery = commandQuery(draft);
  const filteredCommands = availableCommands.filter((command) => {
    if (!slashQuery || slashQuery === "/") {
      return true;
    }

    const descriptionQuery = slashQuery.slice(1);
    return (
      command.command.toLowerCase().includes(slashQuery) ||
      command.description.toLowerCase().includes(descriptionQuery)
    );
  });
  const composerBusy = isBootstrapping || isSending || isExecutingCommand || isUploadingAttachments || deletingAttachmentId !== null;
  const hasComposerContent = draft.trim().length > 0;
  const displayMessages = [...messages, ...localCommandMessages];

  useEffect(() => {
    setLocalCommandMessages([]);
  }, [sessionId]);

  type MessageSegment = {
    type: "text" | "code";
    value: string;
  };

  function splitMessageContent(content: string): MessageSegment[] {
    const segments: MessageSegment[] = [];
    const codeBlockPattern = /```(?:[\w-]+)?\n?([\s\S]*?)```/g;
    let lastIndex = 0;

    for (const match of content.matchAll(codeBlockPattern)) {
      const matchIndex = match.index ?? 0;
      if (matchIndex > lastIndex) {
        const text = content.slice(lastIndex, matchIndex).trim();
        if (text) {
          segments.push({ type: "text", value: text });
        }
      }

      const code = match[1]?.trim();
      if (code) {
        segments.push({ type: "code", value: code });
      }

      lastIndex = matchIndex + match[0].length;
    }

    const trailing = content.slice(lastIndex).trim();
    if (trailing) {
      segments.push({ type: "text", value: trailing });
    }

    return segments.length > 0 ? segments : [{ type: "text", value: content }];
  }

  async function handleCopyMessage(content: string): Promise<void> {
    try {
      if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(content);
      }
    } catch {
      // Ignore clipboard failures in unsupported environments.
    }
  }

  function resetComposerFeedback(): void {
    setComposerError(null);
    setComposerNotice(null);
  }

  function clearComposer(): void {
    setDraft("");
    setIsSlashMenuOpen(false);
  }

  function appendLocalCommandReply(command: string, response: string): void {
    setLocalCommandMessages((current) => [
      ...current,
      { role: "user", content: command },
      { role: "assistant", content: response },
    ]);
  }

  function focusComposer(): void {
    textareaRef.current?.focus();
  }

  function handleDraftChange(event: React.ChangeEvent<HTMLTextAreaElement>): void {
    const nextDraft = event.target.value;
    setDraft(nextDraft);
    setIsSlashMenuOpen(nextDraft.trimStart().startsWith("/"));
    if (composerError) {
      setComposerError(null);
    }
  }

  async function handleFileSelection(event: React.ChangeEvent<HTMLInputElement>): Promise<void> {
    const selectedFiles = Array.from(event.target.files ?? []);
    if (selectedFiles.length === 0) {
      return;
    }

    resetComposerFeedback();
    try {
      await onUploadAttachments(selectedFiles);
      setComposerNotice(
        `Indexed ${selectedFiles.length} file${selectedFiles.length === 1 ? "" : "s"} for this session. Future turns can retrieve the relevant excerpts automatically.`,
      );
      focusComposer();
    } catch (error) {
      setComposerError(error instanceof Error ? error.message : "Unable to upload the selected files.");
    } finally {
      event.target.value = "";
    }
  }

  async function handleRemoveAttachment(attachment: SessionAttachment): Promise<void> {
    resetComposerFeedback();
    try {
      await onDeleteAttachment(attachment.attachment_id);
      setComposerNotice(`${attachment.name} was removed from the active session.`);
    } catch (error) {
      setComposerError(error instanceof Error ? error.message : "Unable to remove the selected attachment.");
    }
  }

  async function executeSlashCommand(input: string): Promise<void> {
    const command = parseSlashCommand(input);
    if (command === null) {
      return;
    }

    if (command.kind === "unsupported") {
      setComposerError(command.message);
      return;
    }

    resetComposerFeedback();
    setIsSlashMenuOpen(false);
    setIsExecutingCommand(true);

    try {
      switch (command.kind) {
        case "mission": {
          clearComposer();
          await onRunMission(command.task);
          break;
        }
        case "show-help":
          clearComposer();
          appendLocalCommandReply(input.trim(), formatCommandList(availableCommands));
          break;
        case "show-skills":
          clearComposer();
          appendLocalCommandReply(input.trim(), formatToolInventorySummary(commandCenterOverview));
          break;
        case "show-memory":
          clearComposer();
          appendLocalCommandReply(input.trim(), formatDurableMemorySummary(commandCenterOverview));
          break;
        case "show-mcp":
          clearComposer();
          appendLocalCommandReply(input.trim(), formatMcpSummary(commandCenterOverview));
          break;
        case "refresh-mcp":
          await onRefreshMcp();
          clearComposer();
          appendLocalCommandReply(input.trim(), "MCP discovery refresh completed for the browser runtime.");
          break;
        case "prepare":
          await onPrepareRuntime();
          clearComposer();
          appendLocalCommandReply(input.trim(), "Runtime preparation completed. Check Activity if you need the detailed status timeline.");
          break;
        case "new-session":
          clearComposer();
          await onNewSession();
          setComposerNotice("Fresh session requested.");
          break;
        case "reload":
          await onReloadTools();
          clearComposer();
          appendLocalCommandReply(input.trim(), "Runtime reload completed. The shared tool inventory has been refreshed.");
          break;
        case "verify":
          await onVerifyRuntime();
          clearComposer();
          appendLocalCommandReply(input.trim(), "Runtime verification completed. Open Command Center if you want the full verification report.");
          break;
      }
    } finally {
      setIsExecutingCommand(false);
    }
  }

  async function handleSlashCommandSelection(command: CommandReference): Promise<void> {
    if (!command.web_available) {
      setComposerError(`${command.command} is only available in the terminal interface.`);
      return;
    }

    if (command.command.includes("<task>")) {
      resetComposerFeedback();
      setDraft((current) => {
        const trimmed = current.trim();
        if (trimmed.startsWith("/mission")) {
          return current;
        }
        if (trimmed.length > 0) {
          return `/mission ${trimmed}`;
        }
        return "/mission ";
      });
      setIsSlashMenuOpen(true);
      focusComposer();
      return;
    }

    await executeSlashCommand(command.command);
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = draft.trim();
    if (!trimmed || composerBusy) {
      return;
    }

    if (trimmed.startsWith("/")) {
      await executeSlashCommand(trimmed);
      return;
    }

    resetComposerFeedback();
    clearComposer();
    await onSendMessage(trimmed);
  }

  async function handleMission(): Promise<void> {
    const trimmed = draft.trim();
    if (!trimmed || composerBusy) {
      return;
    }

    resetComposerFeedback();
    const missionPrompt = trimmed.startsWith("/mission ") ? trimmed.slice(8).trim() : trimmed;
    clearComposer();
    await onRunMission(missionPrompt);
  }

  return (
    <section className="min-h-[72vh] rounded-3xl border border-border-subtle bg-surface-container-lowest shadow-sm">
      <div className="flex items-center justify-between border-b border-border-subtle px-space-lg py-space-md">
        <div className="flex items-center gap-space-md">
          <TerminalSquare className="h-5 w-5 text-primary" />
          <div>
            <h2 className="text-xl font-semibold text-primary">Chat Workspace</h2>
            <p className="text-sm text-text-muted">Session {sessionId ?? "starting"}</p>
          </div>
        </div>

        <div className="flex items-center gap-space-sm">
          <button
            type="button"
            onClick={() => void onNewSession()}
            disabled={isBootstrapping || isSending}
            className="rounded-lg p-space-sm text-text-muted transition hover:bg-surface-container-low hover:text-primary disabled:cursor-not-allowed disabled:opacity-60"
          >
            <RefreshCw className="h-5 w-5" />
          </button>
          <button
            type="button"
            onClick={() => textareaRef.current?.focus()}
            className="rounded-lg p-space-sm text-text-muted transition hover:bg-surface-container-low hover:text-primary"
          >
            <FolderSync className="h-5 w-5" />
          </button>
          <div className="rounded-lg p-space-sm text-emerald-600">
            <CheckCircle2 className="h-5 w-5" />
          </div>
        </div>
      </div>

      <div className="flex min-h-[58vh] flex-col">
        <div className="flex-1 space-y-space-lg overflow-y-auto bg-surface-container-lowest p-space-lg">
          <div className="flex justify-center">
            <div className="rounded-full border border-border-subtle bg-surface-container px-space-md py-space-sm font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted">
              μZephyr runtime initialized. System ready for directives.
            </div>
          </div>

          {displayMessages.length === 0 ? (
            <div className="flex justify-start">
              <div className="flex max-w-[80%] gap-space-md">
                <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-white">
                  <Bot className="h-4 w-4" />
                </div>
                <div className="rounded-2xl rounded-tl-sm border border-border-subtle bg-background px-space-lg py-space-md text-sm leading-6 text-primary">
                  Ask μZephyr to inspect the repo, diagnose runtime issues, or execute a multi-agent mission.
                </div>
              </div>
            </div>
          ) : (
            displayMessages.map((message, index) => {
              if (message.role === "system") {
                return (
                  <div key={`${message.role}-${index}-${message.content.slice(0, 24)}`} className="flex justify-center">
                    <div className="rounded-full border border-border-subtle bg-surface-container px-space-md py-space-sm text-xs text-text-muted">
                      {message.content}
                    </div>
                  </div>
                );
              }

              if (message.role === "user") {
                return (
                  <div key={`${message.role}-${index}-${message.content.slice(0, 24)}`} className="flex justify-end">
                    <div className="max-w-[70%] rounded-2xl rounded-tr-sm border border-border-subtle bg-surface-container px-space-lg py-space-md text-sm leading-6 text-primary shadow-sm">
                      {message.content}
                    </div>
                  </div>
                );
              }

              const segments = splitMessageContent(message.content);
              return (
                <div key={`${message.role}-${index}-${message.content.slice(0, 24)}`} className="flex justify-start">
                  <div className="flex max-w-[80%] gap-space-md">
                    <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-white">
                      <Bot className="h-4 w-4" />
                    </div>
                    <div className="flex flex-col gap-space-md">
                      <div className="rounded-2xl rounded-tl-sm border border-border-subtle bg-background px-space-lg py-space-md text-sm leading-6 text-primary">
                        {segments.map((segment, segmentIndex) =>
                          segment.type === "code" ? (
                            <pre key={`${segment.type}-${segmentIndex}`} className="overflow-x-auto rounded-lg border border-slate-700 bg-[#1A1C1E] p-space-md font-mono text-sm text-slate-200">
                              <code>{segment.value}</code>
                            </pre>
                          ) : (
                            <div key={`${segment.type}-${segmentIndex}`} className="space-y-space-sm">
                              {segment.value.split(/\n\n+/).map((paragraph) => (
                                <p key={paragraph} className="whitespace-pre-wrap break-words">
                                  {paragraph}
                                </p>
                              ))}
                            </div>
                          ),
                        )}
                      </div>
                      <div className="flex gap-space-sm">
                        <button
                          type="button"
                          onClick={() => void handleCopyMessage(message.content)}
                          className="inline-flex items-center gap-1 rounded-md border border-border-subtle bg-surface-container-lowest px-space-sm py-1 text-xs text-text-muted transition hover:text-primary"
                        >
                          <Copy className="h-3.5 w-3.5" />
                          Copy Reply
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })
          )}

          {isSending && !isAssistantStreaming ? (
            <div className="flex justify-start">
              <div className="flex max-w-[80%] gap-space-md">
                <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-white">
                  <Bot className="h-4 w-4" />
                </div>
                <div className="rounded-2xl rounded-tl-sm border border-border-subtle bg-background px-space-lg py-space-md text-sm leading-6 text-primary">
                  {isRunningMission ? "μZephyr Agency is running a mission..." : "μZephyr is thinking..."}
                </div>
              </div>
            </div>
          ) : null}
        </div>

        <div className="border-t border-border-subtle bg-surface-container-lowest p-space-lg">
          <form onSubmit={handleSubmit} className="flex flex-col gap-space-md">
            <input
              ref={fileInputRef}
              type="file"
              multiple
              onChange={(event) => {
                void handleFileSelection(event);
              }}
              className="hidden"
            />

            {attachments.length > 0 ? (
              <div className="space-y-2">
                <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted">
                  Active session attachments
                </p>
                <div className="flex flex-wrap gap-space-sm">
                {attachments.map((attachment) => (
                  <div
                    key={attachment.attachment_id}
                    className="inline-flex items-center gap-2 rounded-full border border-border-subtle bg-surface-container px-space-sm py-2 text-xs text-text-muted"
                  >
                    <Paperclip className="h-3.5 w-3.5" />
                    <span className="font-mono text-[11px] text-primary">{attachment.name}</span>
                    <span>
                      {deletingAttachmentId === attachment.attachment_id
                        ? "Removing..."
                        : formatBytes(attachment.size_bytes)}
                    </span>
                    <button
                      type="button"
                      onClick={() => {
                        void handleRemoveAttachment(attachment);
                      }}
                      disabled={composerBusy}
                      className="rounded-full p-1 text-text-muted transition hover:bg-surface-container-high hover:text-primary"
                      aria-label={`Remove ${attachment.name}`}
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </div>
                ))}
                </div>
              </div>
            ) : null}

            <div className="relative">
              {isSlashMenuOpen ? (
                <div className="absolute bottom-14 left-space-md right-space-md z-10 max-h-64 overflow-y-auto rounded-2xl border border-border-subtle bg-background/95 p-space-sm shadow-lg backdrop-blur">
                  <div className="mb-space-sm flex items-center justify-between border-b border-border-subtle pb-space-sm">
                    <div>
                      <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted">Slash commands</p>
                      <p className="text-xs text-text-muted">Run browser-safe command shortcuts directly from chat.</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setIsSlashMenuOpen(false)}
                      className="rounded-full p-1 text-text-muted transition hover:bg-surface-container-low hover:text-primary"
                      aria-label="Close slash command menu"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>

                  <div className="space-y-2">
                    {filteredCommands.length > 0 ? (
                      filteredCommands.map((command) => (
                        <button
                          key={command.command}
                          type="button"
                          onClick={() => {
                            void handleSlashCommandSelection(command);
                          }}
                          disabled={!command.web_available}
                          className="flex w-full flex-col items-start rounded-xl border border-border-subtle bg-surface-container-lowest px-space-sm py-space-sm text-left transition hover:bg-surface-container-low disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          <span className="font-mono text-sm font-semibold text-primary">{command.command}</span>
                          <span className="mt-1 text-sm leading-6 text-text-muted">{command.description}</span>
                          <span className="mt-2 text-[11px] uppercase tracking-[0.18em] text-text-muted">
                            {command.web_available ? commandExecutionLabel(command) : "Terminal only"}
                          </span>
                        </button>
                      ))
                    ) : (
                      <p className="rounded-xl border border-dashed border-border-subtle px-space-sm py-space-sm text-sm text-text-muted">
                        No slash commands match the current filter.
                      </p>
                    )}
                  </div>
                </div>
              ) : null}

              <textarea
                ref={textareaRef}
                value={draft}
                onChange={handleDraftChange}
                placeholder="Enter command, natural language query, or / to select a tool..."
                rows={4}
                disabled={composerBusy}
                className="h-[100px] w-full resize-none rounded-xl border border-border-subtle bg-surface-container-lowest p-space-md pb-12 text-sm text-primary outline-none transition-all placeholder:text-text-muted focus:border-primary focus:ring-1 focus:ring-primary"
              />
              <div className="absolute bottom-space-md left-space-md flex gap-space-sm text-text-muted">
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={composerBusy}
                  className="transition hover:text-primary disabled:cursor-not-allowed disabled:opacity-60"
                  aria-label="Upload files into the active session attachment index"
                >
                  <Paperclip className="h-5 w-5" />
                </button>
                <button
                  type="button"
                  onClick={() => {
                    resetComposerFeedback();
                    setIsSlashMenuOpen((current) => !current);
                    if (draft.trim().length === 0) {
                      setDraft("/");
                    }
                    focusComposer();
                  }}
                  disabled={composerBusy}
                  className={`transition hover:text-primary disabled:cursor-not-allowed disabled:opacity-60 ${isSlashMenuOpen ? "text-primary" : ""}`}
                  aria-label="Open slash commands"
                >
                  <Code2 className="h-5 w-5" />
                </button>
              </div>
            </div>

            <div className="flex flex-col gap-space-sm sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted">
                <span className="h-2 w-2 rounded-full bg-secondary" />
                Context: {sessionId ? `session-${sessionId.slice(0, 8)}` : "runtime-startup"}
              </div>

              <div className="flex items-center gap-space-md">
                <button
                  type="button"
                  onClick={() => void handleMission()}
                  disabled={composerBusy || !hasComposerContent}
                  className="inline-flex items-center gap-space-sm rounded-lg border border-primary px-space-lg py-[10px] text-sm font-semibold text-primary transition hover:bg-surface-container-high disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <FolderSync className="h-4 w-4" />
                  {isRunningMission ? "Running Mission" : "Run Mission"}
                </button>
                <button
                  type="submit"
                  disabled={composerBusy || !hasComposerContent}
                  className="inline-flex items-center gap-space-sm rounded-lg bg-accent px-space-lg py-[10px] text-sm font-semibold text-white transition hover:bg-secondary disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {composerBusy ? "Working" : "Send Chat"}
                  <Send className="h-4 w-4" />
                </button>
              </div>
            </div>
          </form>

          {composerNotice ? <p className="mt-space-sm text-sm text-primary">{composerNotice}</p> : null}
          {composerError ? <p className="mt-space-sm text-sm text-red-700">{composerError}</p> : null}
          {error ? <p className="mt-space-sm text-sm text-red-700">{error}</p> : null}
        </div>
      </div>
    </section>
  );
}