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

import { McpSetupWalkthrough } from "./McpSetupWalkthrough";
import {
  categorizeToolCatalogEntry,
  sortToolCatalogEntries,
  TOOL_CATALOG_CATEGORY_DEFINITIONS,
} from "../toolCatalog";
import type {
  CommandCenterOverview,
  MemoryBrainRepair,
  MCPConfigurationApplyRequest,
  MCPConfigurationApplyResponse,
  MCPServerStatus,
  MCPToolExecution,
  RuntimeVerification,
  ToolCatalogEntry,
} from "../types/api";

interface CommandCenterPanelProps {
  overview: CommandCenterOverview | null;
  verification: RuntimeVerification | null;
  memoryRepair: MemoryBrainRepair | null;
  error: string | null;
  isLoading: boolean;
  isRefreshingMcp: boolean;
  isApplyingMcp: boolean;
  isVerifying: boolean;
  isRepairingMemory: boolean;
  onRefresh: () => Promise<void>;
  onRefreshMcp: () => Promise<void>;
  onApplyMcp: (payload: MCPConfigurationApplyRequest) => Promise<MCPConfigurationApplyResponse>;
  onVerify: () => Promise<void>;
  onRepairMemory: () => Promise<MemoryBrainRepair>;
}

/**
 * Design reference: frontend/design.md -> Overview, Colors.
 */
export function CommandCenterPanel({
  overview,
  verification,
  memoryRepair,
  error,
  isLoading,
  isRefreshingMcp,
  isApplyingMcp,
  isVerifying: _isVerifying,
  isRepairingMemory,
  onRefresh: _onRefresh,
  onRefreshMcp,
  onApplyMcp,
  onVerify: _onVerify,
  onRepairMemory,
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

  function visibleToolTags(tool: ToolCatalogEntry) {
    const nonGeneralTags = tool.tags.filter((tag) => tag.toLowerCase() !== "general");
    return nonGeneralTags.length ? nonGeneralTags : tool.tags.slice(0, 1);
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

  function mcpCatalogSummary(server: MCPServerStatus) {
    if (server.degraded_reason) {
      return server.degraded_reason;
    }

    const discoveryAge = relativeTimeLabel(server.last_discovered_at);
    if (discoveryAge) {
      return `Inventory refreshed ${discoveryAge}.`;
    }

    if (server.connected) {
      return "Connected with no cached discovery snapshot yet.";
    }

    return "Awaiting the first successful discovery refresh.";
  }

  const allTools = overview?.tools ?? [];
  const mcpServers = overview?.mcp.servers ?? [];
  const toolsByMcpServer = new Map<string, ToolCatalogEntry[]>();
  const serverNameByToolName = new Map<string, string>();

  for (const server of mcpServers) {
    toolsByMcpServer.set(server.name, []);
    for (const toolName of server.discovered_tools) {
      serverNameByToolName.set(toolName, server.name);
    }
  }

  const categorizedTools = new Map(
    TOOL_CATALOG_CATEGORY_DEFINITIONS.map((section) => [section.id, [] as ToolCatalogEntry[]]),
  );
  const unassignedMcpTools: ToolCatalogEntry[] = [];

  for (const tool of allTools) {
    if (tool.source === "mcp") {
      const serverName = serverNameByToolName.get(tool.name);
      if (serverName) {
        toolsByMcpServer.get(serverName)?.push(tool);
      } else {
        unassignedMcpTools.push(tool);
      }
      continue;
    }

    categorizedTools.get(categorizeToolCatalogEntry(tool))?.push(tool);
  }

  const sectionIcons = {
    "code-generation": TerminalSquare,
    memory: Database,
    core: Command,
  } as const;

  const toolCatalogSections = TOOL_CATALOG_CATEGORY_DEFINITIONS.map((section) => ({
    ...section,
    key: section.id,
    icon: sectionIcons[section.id],
    tools: sortToolCatalogEntries(categorizedTools.get(section.id) ?? []),
  }));

  const mcpToolSections: Array<{
    key: string;
    server: MCPServerStatus | null;
    title: string;
    tools: ToolCatalogEntry[];
  }> = mcpServers.map((server) => ({
    key: server.name,
    server,
    title: server.name,
    tools: sortToolCatalogEntries(toolsByMcpServer.get(server.name) ?? []),
  }));

  if (unassignedMcpTools.length) {
    mcpToolSections.push({
      key: "unassigned-mcp",
      server: null,
      title: "Unassigned MCP",
      tools: sortToolCatalogEntries(unassignedMcpTools),
    });
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
        <div className="flex flex-col gap-space-md lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl">
            <h2 className="flex items-center gap-space-sm text-xl font-semibold text-primary">
              <Database className="h-5 w-5" />
              Imported Memory Recovery
            </h2>
            <p className="mt-3 text-sm leading-6 text-text-muted">
              Rebuild timeline.log, truth.md, and entity backlinks from the current knowledge/memories.md import when the
              truth layer is missing, stale, or corrupted after migrating memory from another project snapshot.
            </p>
          </div>
          <button
            type="button"
            onClick={() => void onRepairMemory()}
            disabled={isRepairingMemory}
            className="inline-flex items-center justify-center gap-2 rounded border border-border-subtle px-4 py-3 text-xs font-medium uppercase tracking-[0.18em] text-text-muted transition hover:bg-surface-container-low hover:text-primary disabled:cursor-not-allowed disabled:opacity-60"
          >
            <RotateCcw className={`h-4 w-4 ${isRepairingMemory ? "animate-spin" : ""}`} />
            {isRepairingMemory ? "Repairing" : "Repair Imported Memory"}
          </button>
        </div>

        {memoryRepair ? (
          <div className="mt-space-md rounded-xl border border-emerald-200 bg-emerald-50 p-space-md text-sm leading-6 text-emerald-950">
            <p>{memoryRepair.message}</p>
            <div className="mt-space-sm flex flex-wrap gap-2 text-[11px] uppercase tracking-[0.18em] text-emerald-800">
              <span className="rounded bg-white/70 px-2 py-1">{memoryRepair.fact_count} unique facts</span>
              <span className="rounded bg-white/70 px-2 py-1">{memoryRepair.timeline_line_count} timeline lines</span>
              <span className="rounded bg-white/70 px-2 py-1">{memoryRepair.entity_file_count} entity files</span>
              <span className="rounded bg-white/70 px-2 py-1">{memoryRepair.duplicate_count} duplicates skipped</span>
              <span className="rounded bg-white/70 px-2 py-1">{memoryRepair.backup_paths.length} backups</span>
            </div>
            <div className="mt-space-sm space-y-2 font-mono text-xs text-emerald-900/80">
              <div>timeline: {memoryRepair.timeline_path}</div>
              <div>truth: {memoryRepair.truth_path}</div>
            </div>
          </div>
        ) : (
          <p className="mt-space-md text-sm leading-6 text-text-muted">
            Use this recovery action after importing an older memories.md snapshot that does not bring forward a valid
            timeline.log or truth.md.
          </p>
        )}
      </article>

      <McpSetupWalkthrough
        overview={overview?.mcp ?? null}
        isRefreshingMcp={isRefreshingMcp}
        isApplyingMcp={isApplyingMcp}
        onRefreshMcp={onRefreshMcp}
        onApplyMcp={onApplyMcp}
      />

      <article className="rounded-xl border border-border-subtle bg-surface-container-lowest p-space-md">
        <div className="flex items-center justify-between border-b border-border-subtle pb-space-sm">
          <h2 className="flex items-center gap-space-sm text-xl font-semibold text-primary">
            <Boxes className="h-5 w-5" />
            Tool Catalog
          </h2>
          <span className="font-mono text-xs uppercase tracking-[0.18em] text-text-muted">{overview?.tools.length ?? 0} tools</span>
        </div>
        {overview?.tools.length ? (
          <>
            <div className="mt-space-md grid gap-space-md xl:grid-cols-3">
              {toolCatalogSections.map((section) => {
                const SectionIcon = section.icon;
                return (
                  <article key={section.key} className="rounded-xl border border-border-subtle bg-background p-space-md">
                    <div className="flex items-start justify-between gap-space-sm border-b border-border-subtle pb-space-sm">
                      <div className="flex items-start gap-space-sm">
                        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-surface-container text-primary">
                          <SectionIcon className="h-5 w-5" />
                        </div>
                        <div>
                          <h3 className="text-base font-semibold text-primary">{section.title}</h3>
                          <p className="mt-1 text-sm leading-6 text-text-muted">{section.description}</p>
                        </div>
                      </div>
                      <span className="rounded bg-surface-container px-2 py-1 font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted">
                        {section.tools.length}
                      </span>
                    </div>

                    <div className="mt-space-md max-h-96 overflow-y-auto pr-1">
                      {section.tools.length ? (
                        <div className="grid gap-space-sm">
                          {section.tools.map((tool) => {
                            const Icon = toolIcon(tool);
                            return (
                              <article
                                key={`${section.key}-${tool.source}-${tool.name}`}
                                title={tool.description}
                                className="rounded-lg border border-border-subtle bg-surface-container-lowest p-space-sm transition-colors hover:border-primary"
                              >
                                <div className="flex items-start gap-space-sm">
                                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-surface-container text-primary">
                                    <Icon className="h-4 w-4" />
                                  </div>
                                  <div className="min-w-0 flex-1">
                                    <div className="truncate text-sm font-semibold text-primary">{tool.name}</div>
                                    <div className="mt-2 flex flex-wrap gap-2">
                                      <span className="rounded bg-surface-container px-2 py-1 font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted">
                                        {tool.source_label}
                                      </span>
                                      {visibleToolTags(tool).map((tag) => (
                                        <span
                                          key={`${tool.name}-${tag}`}
                                          className="rounded bg-surface-container px-2 py-1 text-[11px] uppercase tracking-[0.18em] text-text-muted"
                                        >
                                          {tag}
                                        </span>
                                      ))}
                                    </div>
                                  </div>
                                </div>
                              </article>
                            );
                          })}
                        </div>
                      ) : (
                        <p className="text-sm leading-6 text-text-muted">{section.emptyMessage}</p>
                      )}
                    </div>
                  </article>
                );
              })}
            </div>

            <article className="mt-space-md rounded-xl border border-border-subtle bg-background p-space-md">
              <div className="flex items-start justify-between gap-space-sm border-b border-border-subtle pb-space-sm">
                <div className="flex items-start gap-space-sm">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-surface-container text-primary">
                    <PlugZap className="h-5 w-5" />
                  </div>
                  <div>
                    <h3 className="text-base font-semibold text-primary">MCP Tools</h3>
                    <p className="mt-1 text-sm leading-6 text-text-muted">
                      Remote tool inventories grouped by MCP server so each integration stays isolated in its own pane.
                    </p>
                  </div>
                </div>
                <span className="rounded bg-surface-container px-2 py-1 font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted">
                  {allTools.filter((tool) => tool.source === "mcp").length}
                </span>
              </div>

              <div className="mt-space-md grid gap-space-md xl:grid-cols-2">
                {mcpToolSections.length ? (
                  mcpToolSections.map((section) => (
                    <article key={section.key} className="rounded-xl border border-border-subtle bg-surface-container-lowest p-space-md">
                      <div className="flex items-start justify-between gap-space-sm border-b border-border-subtle pb-space-sm">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            {section.server ? <span className={`h-2.5 w-2.5 rounded-full ${mcpStateDot(section.server)}`} /> : null}
                            <h4 className="truncate text-sm font-semibold uppercase tracking-[0.18em] text-primary">{section.title}</h4>
                          </div>
                          <p className="mt-2 text-sm leading-6 text-text-muted">
                            {section.server ? mcpCatalogSummary(section.server) : "MCP tools visible to the runtime that are not tied to a live server snapshot."}
                          </p>
                        </div>
                        <div className="flex shrink-0 flex-col items-end gap-2">
                          {section.server ? (
                            <span className="rounded bg-surface-container px-2 py-1 font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted">
                              {mcpStateLabel(section.server)}
                            </span>
                          ) : null}
                          <span className="rounded bg-surface-container px-2 py-1 font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted">
                            {section.tools.length} tools
                          </span>
                        </div>
                      </div>

                      <div className="mt-space-md max-h-96 overflow-y-auto pr-1">
                        {section.tools.length ? (
                          <div className="flex flex-wrap gap-2">
                            {section.tools.map((tool) => (
                              <div
                                key={`${section.key}-${tool.name}`}
                                title={tool.description}
                                className="rounded-lg border border-border-subtle bg-background px-3 py-2 text-sm font-medium text-primary transition-colors hover:border-primary"
                              >
                                {tool.name}
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p className="text-sm leading-6 text-text-muted">
                            {section.server
                              ? "No tools are currently visible for this MCP server. Run Refresh MCP discovery after the server is ready."
                              : "No unassigned MCP tools are currently visible."}
                          </p>
                        )}
                      </div>
                    </article>
                  ))
                ) : (
                  <p className="text-sm leading-6 text-text-muted">No MCP tools are currently visible to the web command center.</p>
                )}
              </div>
            </article>
          </>
        ) : (
          <p className="mt-space-md text-sm text-text-muted">
            {isLoading ? "Loading tool inventory..." : "No tools are currently visible to the web command center."}
          </p>
        )}
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