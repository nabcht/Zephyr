import {
  ArrowRightLeft,
  Boxes,
  CheckCircle2,
  Command,
  Database,
  Play,
  PlugZap,
  RefreshCw,
  RotateCcw,
  Router,
  Search,
  TerminalSquare,
  Wrench,
} from "lucide-react";

import type { CommandCenterOverview, MCPServerStatus, MCPToolExecution, RuntimeVerification, ToolCatalogEntry } from "../types/api";

interface CommandCenterPanelProps {
  overview: CommandCenterOverview | null;
  verification: RuntimeVerification | null;
  error: string | null;
  isLoading: boolean;
  isRefreshingMcp: boolean;
  isVerifying: boolean;
  onRefresh: () => Promise<void>;
  onRefreshMcp: () => Promise<void>;
  onVerify: () => Promise<void>;
}

/**
 * Design reference: frontend/design.md -> Overview, Colors.
 */
export function CommandCenterPanel({
  overview,
  verification,
  error,
  isLoading,
  isRefreshingMcp,
  isVerifying: _isVerifying,
  onRefresh: _onRefresh,
  onRefreshMcp,
  onVerify: _onVerify,
}: CommandCenterPanelProps) {
  function commandIcon(command: string) {
    if (command.includes("verify")) {
      return CheckCircle2;
    }
    if (command.includes("mission")) {
      return Play;
    }
    if (command.includes("memory")) {
      return Database;
    }
    if (command.includes("mcp")) {
      return PlugZap;
    }
    if (command.includes("reload")) {
      return RotateCcw;
    }
    if (command.includes("search") || command.includes("skill")) {
      return Search;
    }
    return ArrowRightLeft;
  }

  function toolIcon(tool: ToolCatalogEntry) {
    const name = `${tool.name} ${tool.tags.join(" ")}`.toLowerCase();
    if (name.includes("sql") || name.includes("database")) {
      return Database;
    }
    if (name.includes("terminal") || name.includes("shell") || name.includes("bash")) {
      return TerminalSquare;
    }
    if (tool.source === "mcp") {
      return PlugZap;
    }
    if (tool.source === "builtin") {
      return Wrench;
    }
    return Command;
  }

  function verificationLines(): string[] {
    if (!verification) {
      return [
        "[INFO] Awaiting browser-side verification run.",
        "[INFO] Use Verify Runtime from the top navigation to mirror the CLI /verify flow.",
      ];
    }

    const lines = [
      `[INFO] Skill integrity: ${verification.valid_skills.length} valid, ${verification.repaired_skills.length} repaired, ${verification.broken_skills.length} broken.`,
      ...verification.repaired_skills.map((line) => `[INFO] Repaired: ${line}`),
      ...verification.broken_skills.map((line) => `[WARN] Broken: ${line}`),
      ...verification.sandbox_readiness.map((line) => `[INFO] ${line}`),
      ...verification.truth_synthesis.map((line) => `[INFO] ${line}`),
      ...verification.startup_guidance.map((line) => `[WARN] ${line}`),
    ];

    if (verification.eval_summary) {
      lines.push(`[INFO] ${verification.eval_summary}`);
    }

    return lines;
  }

  function toneForLine(line: string) {
    const lowered = line.toLowerCase();
    if (lowered.includes("warn") || lowered.includes("warning")) {
      return "text-amber-400";
    }
    if (lowered.includes("error") || lowered.includes("broken")) {
      return "text-red-400";
    }
    return "text-emerald-400";
  }

  function mcpStateDot(server: MCPServerStatus) {
    if (server.state === "error") {
      return "bg-red-500";
    }
    if (server.state === "connected") {
      return "bg-emerald-500";
    }
    return "bg-amber-500";
  }

  function mcpStateLabel(server: MCPServerStatus) {
    if (server.state === "error") {
      return "Error";
    }
    if (server.state === "connected") {
      return "Connected";
    }
    return "Ready";
  }

  function relativeTimeLabel(value: string | null) {
    if (!value) {
      return null;
    }

    const timestamp = Date.parse(value);
    if (Number.isNaN(timestamp)) {
      return value;
    }

    const deltaSeconds = Math.max(0, Math.round((Date.now() - timestamp) / 1000));
    if (deltaSeconds < 60) {
      return `${deltaSeconds}s ago`;
    }

    const deltaMinutes = Math.round(deltaSeconds / 60);
    if (deltaMinutes < 60) {
      return `${deltaMinutes}m ago`;
    }

    const deltaHours = Math.round(deltaMinutes / 60);
    if (deltaHours < 24) {
      return `${deltaHours}h ago`;
    }

    const deltaDays = Math.round(deltaHours / 24);
    return `${deltaDays}d ago`;
  }

  function serverInventoryLabel(server: MCPServerStatus) {
    if (server.discovered_tools.length) {
      return `Cached tools: ${server.discovered_tools.join(", ")}`;
    }
    if (server.last_discovered_at) {
      return "Cached inventory is empty.";
    }
    return `${server.command} ${server.args.join(" ")}`.trim();
  }

  function executionPreview(execution: MCPToolExecution) {
    if (execution.structured_content_preview) {
      return execution.structured_content_preview;
    }
    return execution.display_text;
  }

  return (
    <section className="space-y-space-lg">
      {error ? (
        <article className="rounded-xl border border-red-200 bg-red-50 p-space-md text-sm leading-6 text-red-900">
          {error}
        </article>
      ) : null}

      <div className="grid gap-space-md lg:grid-cols-3">
        <article className="lg:col-span-2 rounded-xl border border-border-subtle bg-surface-container-lowest p-space-md">
          <div className="flex items-center justify-between border-b border-border-subtle pb-space-sm">
            <h2 className="flex items-center gap-space-sm text-xl font-semibold text-primary">
              <Command className="h-5 w-5" />
              Command Map
            </h2>
          </div>
          <div className="mt-space-md grid gap-space-sm md:grid-cols-2">
            {(overview?.commands ?? []).map((command) => {
              const Icon = commandIcon(command.command);
              return (
                <div key={command.command} className="rounded-lg p-space-sm transition-colors hover:bg-surface-container-low">
                  <div className="flex items-start gap-space-sm">
                    <Icon className={`mt-1 h-4 w-4 ${command.web_available ? "text-accent" : "text-text-muted"}`} />
                    <div>
                      <div className="font-mono text-sm font-semibold text-primary">{command.command}</div>
                      <div className="mt-1 text-sm leading-6 text-text-muted">{command.description}</div>
                      <div className="mt-2 text-xs uppercase tracking-[0.18em] text-text-muted">
                        {command.web_available ? command.web_label ?? "Web" : "Terminal Only"}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
            {overview === null && isLoading ? <p className="text-sm text-text-muted">Loading command coverage...</p> : null}
          </div>
        </article>

        <article className="rounded-xl border border-border-subtle bg-surface-container-lowest p-space-md">
          <div className="flex items-center justify-between border-b border-border-subtle pb-space-sm">
            <h2 className="flex items-center gap-space-sm text-xl font-semibold text-primary">
              <Router className="h-5 w-5" />
              MCP Servers
            </h2>
            <button
              type="button"
              onClick={() => void onRefreshMcp()}
              disabled={isRefreshingMcp}
              className="inline-flex items-center gap-2 rounded border border-border-subtle px-3 py-2 text-xs font-medium uppercase tracking-[0.18em] text-text-muted transition hover:bg-surface-container-low hover:text-primary disabled:cursor-not-allowed disabled:opacity-60"
            >
              <RefreshCw className={`h-4 w-4 ${isRefreshingMcp ? "animate-spin" : ""}`} />
              {isRefreshingMcp ? "Refreshing" : "Refresh MCP"}
            </button>
          </div>
          <p className="mt-3 text-sm leading-6 text-text-muted">
            {overview?.mcp.message ?? "Loading MCP status..."}
          </p>
          <div className="mt-space-md space-y-space-sm">
            {overview?.mcp.servers.length ? (
              overview.mcp.servers.map((server) => (
                <article key={server.name} className="rounded-lg border border-border-subtle bg-background px-space-sm py-space-sm">
                  <div className="flex items-center justify-between gap-space-sm">
                    <div className="flex items-center gap-space-sm">
                      <span className={`h-2 w-2 rounded-full ${mcpStateDot(server)}`} />
                      <span className="font-mono text-sm text-primary">{server.name}</span>
                    </div>
                    <span className="text-xs uppercase tracking-[0.18em] text-text-muted">
                      {mcpStateLabel(server)}
                    </span>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-text-muted">
                    {serverInventoryLabel(server)}
                  </p>
                  <div className="mt-2 flex flex-wrap gap-2 text-[11px] uppercase tracking-[0.18em] text-text-muted">
                    <span className="rounded bg-surface-container px-2 py-1">prefix {server.tool_prefix}</span>
                    <span className="rounded bg-surface-container px-2 py-1">
                      discovery {relativeTimeLabel(server.last_discovered_at) ?? "pending"}
                    </span>
                    <span className="rounded bg-surface-container px-2 py-1">
                      connected {relativeTimeLabel(server.last_successful_connection_at) ?? "never"}
                    </span>
                    {server.last_error_kind ? <span className="rounded bg-red-50 px-2 py-1 text-red-700">{server.last_error_kind}</span> : null}
                    {server.last_error_tool_name ? <span className="rounded bg-surface-container px-2 py-1">tool {server.last_error_tool_name}</span> : null}
                  </div>
                  {server.last_discovered_at ? (
                    <p className="mt-2 rounded bg-surface-container px-3 py-2 text-sm leading-6 text-text-muted">
                      Inventory is cached from the last successful MCP discovery refresh.
                    </p>
                  ) : null}
                  {server.degraded_reason && !server.last_error ? (
                    <p className="mt-2 rounded bg-amber-50 px-3 py-2 text-sm leading-6 text-amber-900">{server.degraded_reason}</p>
                  ) : null}
                  {server.last_error && server.last_discovered_at ? (
                    <p className="mt-2 rounded bg-amber-50 px-3 py-2 text-sm leading-6 text-amber-900">
                      Showing cached inventory from the last successful discovery refresh while the latest refresh error is active.
                    </p>
                  ) : null}
                  {server.last_error ? (
                    <p className="mt-2 rounded bg-red-50 px-3 py-2 text-sm leading-6 text-red-900">{server.last_error}</p>
                  ) : null}
                </article>
              ))
            ) : (
              <article className="rounded-lg border border-border-subtle bg-background px-space-sm py-space-sm text-sm leading-6 text-text-muted">
                {overview?.mcp.message ?? "Loading MCP status..."}
              </article>
            )}
          </div>
          <div className="mt-space-md border-t border-border-subtle pt-space-sm">
            <div className="text-xs uppercase tracking-[0.18em] text-text-muted">Recent MCP Results</div>
            <div className="mt-space-sm space-y-space-sm">
              {overview?.mcp.recent_executions.length ? (
                overview.mcp.recent_executions.map((execution) => (
                  <article key={`${execution.tool_name}-${execution.executed_at}`} className="rounded-lg border border-border-subtle bg-background px-space-sm py-space-sm">
                    <div className="flex items-center justify-between gap-space-sm">
                      <span className="font-mono text-sm text-primary">{execution.tool_name}</span>
                      <span className="text-xs uppercase tracking-[0.18em] text-text-muted">
                        {relativeTimeLabel(execution.executed_at) ?? execution.executed_at}
                      </span>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-2 text-[11px] uppercase tracking-[0.18em] text-text-muted">
                      {execution.structured_content_type ? (
                        <span className="rounded bg-surface-container px-2 py-1">{execution.structured_content_type}</span>
                      ) : null}
                      {execution.error_type ? (
                        <span className="rounded bg-red-50 px-2 py-1 text-red-700">{execution.error_type}</span>
                      ) : null}
                      {execution.is_error ? (
                        <span className="rounded bg-red-50 px-2 py-1 text-red-700">error</span>
                      ) : (
                        <span className="rounded bg-surface-container px-2 py-1">ok</span>
                      )}
                    </div>
                    <p className={`mt-2 text-sm leading-6 ${execution.is_error ? "text-red-900" : "text-text-muted"}`}>
                      {executionPreview(execution)}
                    </p>
                  </article>
                ))
              ) : (
                <p className="text-sm leading-6 text-text-muted">No MCP tool executions recorded yet.</p>
              )}
            </div>
          </div>
        </article>
      </div>

      <article className="rounded-xl border border-border-subtle bg-surface-container-lowest p-space-md">
        <div className="flex items-center justify-between border-b border-border-subtle pb-space-sm">
          <h2 className="flex items-center gap-space-sm text-xl font-semibold text-primary">
            <Boxes className="h-5 w-5" />
            Tool Catalog
          </h2>
          <span className="font-mono text-xs uppercase tracking-[0.18em] text-text-muted">{overview?.tools.length ?? 0} tools</span>
        </div>
        <div className="mt-space-md grid gap-space-md grid-cols-2 md:grid-cols-4">
          {overview?.tools.length ? (
            overview.tools.map((tool) => {
              const Icon = toolIcon(tool);
              return (
                <article key={`${tool.source}-${tool.name}`} className="flex flex-col items-center justify-center gap-space-sm rounded border border-border-subtle p-space-sm text-center transition-colors hover:border-primary">
                  <Icon className="h-8 w-8 text-primary" />
                  <div className="text-sm font-semibold text-primary">{tool.name}</div>
                  <div className="rounded bg-surface-container px-2 py-1 font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted">
                    {tool.source_label}
                  </div>
                </article>
              );
            })
          ) : (
            <p className="col-span-full text-sm text-text-muted">
              {isLoading ? "Loading tool inventory..." : "No tools are currently visible to the web command center."}
            </p>
          )}
        </div>
      </article>

      <article className="rounded-xl border border-primary bg-primary p-space-md text-white shadow-sm">
        <div className="mb-space-sm flex items-center gap-space-sm border-b border-white/15 pb-space-sm">
          <CheckCircle2 className="h-4 w-4 text-white/80" />
          <h3 className="font-mono text-sm uppercase tracking-[0.2em] text-white/80">System Integrity Verification</h3>
        </div>
        <div className="space-y-2 font-mono text-sm text-white/85">
          {verificationLines().map((line, index) => (
            <div key={`${line}-${index}`} className="flex gap-space-sm">
              <span className="w-16 shrink-0 text-white/40">step {String(index + 1).padStart(2, "0")}</span>
              <span className={toneForLine(line)}>{line}</span>
            </div>
          ))}
          <div className="mt-space-sm flex gap-space-sm text-white/70">
            <span className="w-16 shrink-0">~ $</span>
            <span className="animate-pulse">_</span>
          </div>
        </div>
      </article>
    </section>
  );
}