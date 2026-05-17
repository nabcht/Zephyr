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
} from "lucide-react";
import { useRef, useState } from "react";

import type { SessionMessage } from "../types/api";

interface ChatWorkspaceProps {
  sessionId: string | null;
  messages: SessionMessage[];
  error: string | null;
  isBootstrapping: boolean;
  isSending: boolean;
  isRunningMission: boolean;
  onNewSession: () => Promise<void>;
  onSendMessage: (message: string) => Promise<void>;
  onRunMission: (message: string) => Promise<void>;
}

/**
 * Design reference: frontend/design.md -> Overview, Colors.
 */
export function ChatWorkspace({
  sessionId,
  messages,
  error,
  isBootstrapping,
  isSending,
  isRunningMission,
  onNewSession,
  onSendMessage,
  onRunMission,
}: ChatWorkspaceProps) {
  const [draft, setDraft] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const isAssistantStreaming = isSending && messages[messages.length - 1]?.role === "assistant";

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

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = draft.trim();
    if (!trimmed || isSending || isBootstrapping) {
      return;
    }

    setDraft("");
    await onSendMessage(trimmed);
  }

  async function handleMission(): Promise<void> {
    const trimmed = draft.trim();
    if (!trimmed || isSending || isBootstrapping) {
      return;
    }

    setDraft("");
    await onRunMission(trimmed);
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

          {messages.length === 0 ? (
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
            messages.map((message, index) => {
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
            <div className="relative">
              <textarea
                ref={textareaRef}
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                placeholder="Enter command, natural language query, or / to select a tool..."
                rows={4}
                disabled={isBootstrapping || isSending}
                className="h-[100px] w-full resize-none rounded-xl border border-border-subtle bg-surface-container-lowest p-space-md pb-12 text-sm text-primary outline-none transition-all placeholder:text-text-muted focus:border-primary focus:ring-1 focus:ring-primary"
              />
              <div className="absolute bottom-space-md left-space-md flex gap-space-sm text-text-muted">
                <button type="button" className="transition hover:text-primary">
                  <Paperclip className="h-5 w-5" />
                </button>
                <button type="button" className="transition hover:text-primary">
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
                  disabled={isBootstrapping || isSending || draft.trim().length === 0}
                  className="inline-flex items-center gap-space-sm rounded-lg border border-primary px-space-lg py-[10px] text-sm font-semibold text-primary transition hover:bg-surface-container-high disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <FolderSync className="h-4 w-4" />
                  {isRunningMission ? "Running Mission" : "Run Mission"}
                </button>
                <button
                  type="submit"
                  disabled={isBootstrapping || isSending || draft.trim().length === 0}
                  className="inline-flex items-center gap-space-sm rounded-lg bg-accent px-space-lg py-[10px] text-sm font-semibold text-white transition hover:bg-secondary disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isSending ? "Sending" : "Send Chat"}
                  <Send className="h-4 w-4" />
                </button>
              </div>
            </div>
          </form>

          {error ? <p className="mt-space-sm text-sm text-red-700">{error}</p> : null}
        </div>
      </div>
    </section>
  );
}