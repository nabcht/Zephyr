import { Copy, Link2, Plus, PlugZap, RefreshCw, Save, Server, TerminalSquare, Trash2 } from "lucide-react";
import { type ReactNode, useEffect, useState } from "react";

import type {
  MCPConfigurationApplyRequest,
  MCPConfigurationApplyResponse,
  MCPConfigurationFormat,
  MCPConfiguredServer,
  MCPOverview,
} from "../types/api";

type SetupMode = "remote" | "stdio";
type RemoteLauncher = "npx" | "uvx";

interface McpSetupWalkthroughProps {
  overview: MCPOverview | null;
  isRefreshingMcp: boolean;
  isApplyingMcp: boolean;
  onRefreshMcp: () => Promise<void>;
  onApplyMcp: (payload: MCPConfigurationApplyRequest) => Promise<MCPConfigurationApplyResponse>;
}

interface ParsedVariables {
  env: Record<string, string>;
  invalidLines: string[];
}

interface ServerDraft {
  id: string;
  mode: SetupMode;
  remoteLauncher: RemoteLauncher;
  name: string;
  toolPrefix: string;
  serverUrl: string;
  workingDirectory: string;
  stdioCommand: string;
  stdioArgs: string;
  variableLines: string;
}

interface NormalizedDraft {
  id: string;
  server: MCPConfiguredServer;
  launcherPreview: string;
  invalidLines: string[];
  missingPrimaryInput: boolean;
}

const fieldClassName =
  "mt-2 w-full rounded-xl border border-border-subtle bg-background px-3 py-3 text-sm text-primary outline-none transition placeholder:text-text-muted focus:border-primary focus:ring-1 focus:ring-primary";
const textareaClassName = `${fieldClassName} min-h-[128px] resize-y`;

function StepCard({ step, title, description, children }: { step: string; title: string; description: string; children: ReactNode }) {
  return (
    <article className="rounded-xl border border-border-subtle bg-background p-space-md">
      <div className="flex items-start gap-space-sm">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-surface-container text-xs font-semibold uppercase tracking-[0.18em] text-primary">
          {step}
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="text-base font-semibold text-primary">{title}</h3>
          <p className="mt-1 text-sm leading-6 text-text-muted">{description}</p>
        </div>
      </div>
      <div className="mt-space-md">{children}</div>
    </article>
  );
}

function parseVariableLines(raw: string): ParsedVariables {
  const env: Record<string, string> = {};
  const invalidLines: string[] = [];

  for (const line of raw.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed) {
      continue;
    }

    const separatorIndex = trimmed.indexOf("=");
    if (separatorIndex <= 0) {
      invalidLines.push(trimmed);
      continue;
    }

    const key = trimmed.slice(0, separatorIndex).trim();
    const value = trimmed.slice(separatorIndex + 1).trim();
    if (!key) {
      invalidLines.push(trimmed);
      continue;
    }

    env[key] = value;
  }

  return { env, invalidLines };
}

function parseArgumentLines(raw: string): string[] {
  return raw
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

function formatCommandPreview(command: string, args: string[]): string {
  if (!args.length) {
    return command;
  }

  return `${command} ${args
    .map((value) => (value.includes(" ") ? `"${value}"` : value))
    .join(" ")}`;
}

function createServerDraft(index: number): ServerDraft {
  return {
    id: `server-${Date.now()}-${index}-${Math.random().toString(16).slice(2)}`,
    mode: "remote",
    remoteLauncher: "npx",
    name: index === 1 ? "archive" : `server-${index}`,
    toolPrefix: "mcp",
    serverUrl: "",
    workingDirectory: "",
    stdioCommand: "python",
    stdioArgs: "",
    variableLines: "",
  };
}

function normalizeDraft(draft: ServerDraft, index: number): NormalizedDraft {
  const parsedVariables = parseVariableLines(draft.variableLines);
  const name = draft.name.trim() || `server-${index}`;
  const toolPrefix = draft.toolPrefix.trim() || "mcp";
  const cwd = draft.workingDirectory.trim();
  const command = draft.mode === "remote" ? (draft.remoteLauncher === "uvx" ? "uvx" : "npx") : draft.stdioCommand.trim() || "python";
  const remoteUrl = draft.serverUrl.trim();
  const args =
    draft.mode === "remote"
      ? draft.remoteLauncher === "uvx"
        ? ["mcp-remote", remoteUrl || "https://your-mcp-server.example.com/mcp"]
        : ["-y", "mcp-remote", remoteUrl || "https://your-mcp-server.example.com/mcp"]
      : parseArgumentLines(draft.stdioArgs);

  return {
    id: draft.id,
    server: {
      name,
      command,
      args,
      env: parsedVariables.env,
      cwd: cwd || null,
      tool_prefix: toolPrefix,
    },
    launcherPreview: formatCommandPreview(command, args),
    invalidLines: parsedVariables.invalidLines,
    missingPrimaryInput: draft.mode === "remote" ? !remoteUrl : !draft.stdioCommand.trim(),
  };
}

function quoteEnvValue(value: string): string {
  if (!value) {
    return '""';
  }

  if (!value.includes("#") && !value.includes("'") && !/\s/.test(value)) {
    return value;
  }

  if (!value.includes("'")) {
    return `'${value}'`;
  }

  return `"${value.split('"').join('\\"')}"`;
}

function buildEnvAssignments(request: MCPConfigurationApplyRequest): Record<string, string> {
  const assignments: Record<string, string> = {
    MCP_ENABLED: request.enable_mcp ? "true" : "false",
    EXTERNAL_SUBPROCESS_INTEGRATIONS_ENABLED: request.enable_external_integrations ? "true" : "false",
  };

  if (request.format === "json") {
    assignments.MCP_SERVERS_JSON = JSON.stringify(
      request.servers.map((server) => ({
        name: server.name,
        command: server.command,
        args: server.args,
        ...(server.env && Object.keys(server.env).length ? { env: server.env } : {}),
        ...(server.cwd ? { cwd: server.cwd } : {}),
        tool_prefix: server.tool_prefix,
      })),
    );
    return assignments;
  }

  if (request.format === "single") {
    const server = request.servers[0];
    assignments.MCP_SERVER_NAME = server.name;
    assignments.MCP_SERVER_COMMAND = server.command;
    assignments.MCP_SERVER_ARGS = JSON.stringify(server.args);
    assignments.MCP_TOOL_PREFIX = server.tool_prefix;
    if (server.cwd) {
      assignments.MCP_SERVER_CWD = server.cwd;
    }
    if (Object.keys(server.env).length) {
      assignments.MCP_SERVER_ENV_JSON = JSON.stringify(server.env);
    }
    return assignments;
  }

  request.servers.forEach((server, index) => {
    const prefix = `MCP_SERVER_${index + 1}_`;
    assignments[`${prefix}NAME`] = server.name;
    assignments[`${prefix}COMMAND`] = server.command;
    assignments[`${prefix}ARGS`] = JSON.stringify(server.args);
    assignments[`${prefix}TOOL_PREFIX`] = server.tool_prefix;
    if (server.cwd) {
      assignments[`${prefix}CWD`] = server.cwd;
    }
    if (Object.keys(server.env).length) {
      assignments[`${prefix}ENV_JSON`] = JSON.stringify(server.env);
    }
  });
  return assignments;
}

function renderEnvBlock(request: MCPConfigurationApplyRequest): string {
  return Object.entries(buildEnvAssignments(request))
    .map(([key, value]) => `${key}=${quoteEnvValue(value)}`)
    .join("\n");
}

function formatBadgeLabel(format: MCPConfigurationFormat): string {
  if (format === "single") {
    return "Single-server vars";
  }
  if (format === "indexed") {
    return "Indexed vars";
  }
  return "MCP_SERVERS_JSON";
}

export function McpSetupWalkthrough({ overview, isRefreshingMcp, isApplyingMcp, onRefreshMcp, onApplyMcp }: McpSetupWalkthroughProps) {
  const [serverDrafts, setServerDrafts] = useState<ServerDraft[]>(() => [createServerDraft(1)]);
  const [configFormat, setConfigFormat] = useState<MCPConfigurationFormat>("single");
  const [copyState, setCopyState] = useState<"idle" | "copied" | "error">("idle");
  const [applyState, setApplyState] = useState<{ tone: "idle" | "success" | "error"; message: string }>({ tone: "idle", message: "" });
  const [lastApplyResponse, setLastApplyResponse] = useState<MCPConfigurationApplyResponse | null>(null);

  useEffect(() => {
    if (serverDrafts.length > 1 && configFormat === "single") {
      setConfigFormat("indexed");
    }
  }, [configFormat, serverDrafts.length]);

  const normalizedDrafts = serverDrafts.map((draft, index) => normalizeDraft(draft, index + 1));
  const invalidLineCount = normalizedDrafts.reduce((total, draft) => total + draft.invalidLines.length, 0);
  const missingPrimaryCount = normalizedDrafts.reduce((total, draft) => total + (draft.missingPrimaryInput ? 1 : 0), 0);
  const hasBlockingErrors = invalidLineCount > 0 || missingPrimaryCount > 0;

  const applyRequest: MCPConfigurationApplyRequest = {
    format: configFormat,
    enable_mcp: true,
    enable_external_integrations: true,
    servers: normalizedDrafts.map((draft) => draft.server),
  };
  const envBlock = renderEnvBlock(applyRequest);
  const runtimeFlagsEnabled = Boolean(overview?.enabled) && Boolean(overview?.external_integrations_enabled);
  const copyDisabled = hasBlockingErrors;

  function updateDraft(id: string, patch: Partial<ServerDraft>): void {
    setServerDrafts((current) => current.map((draft) => (draft.id === id ? { ...draft, ...patch } : draft)));
  }

  function addServer(): void {
    setServerDrafts((current) => [...current, createServerDraft(current.length + 1)]);
    setApplyState({ tone: "idle", message: "" });
  }

  function removeServer(id: string): void {
    setServerDrafts((current) => (current.length > 1 ? current.filter((draft) => draft.id !== id) : current));
    setApplyState({ tone: "idle", message: "" });
  }

  async function handleCopyConfig(): Promise<void> {
    if (copyDisabled) {
      return;
    }

    try {
      if (typeof navigator === "undefined" || !navigator.clipboard?.writeText) {
        throw new Error("Clipboard API unavailable.");
      }

      await navigator.clipboard.writeText(envBlock);
      setCopyState("copied");
      if (typeof window !== "undefined") {
        window.setTimeout(() => {
          setCopyState("idle");
        }, 1800);
      }
    } catch {
      setCopyState("error");
    }
  }

  async function handleApplyConfig(): Promise<void> {
    if (hasBlockingErrors) {
      setApplyState({ tone: "error", message: "Resolve the missing URL or variable formatting issues before applying the configuration." });
      return;
    }

    try {
      const response = await onApplyMcp(applyRequest);
      setLastApplyResponse(response);
      setApplyState({ tone: "success", message: response.message });
    } catch (error) {
      setApplyState({ tone: "error", message: error instanceof Error ? error.message : "Failed to apply MCP configuration." });
    }
  }

  return (
    <article className="rounded-xl border border-border-subtle bg-surface-container-lowest p-space-md">
      <div className="flex flex-col gap-space-md border-b border-border-subtle pb-space-md lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-3xl">
          <div className="text-xs uppercase tracking-[0.22em] text-accent">Walkthrough</div>
          <h2 className="mt-2 flex items-center gap-space-sm text-xl font-semibold text-primary">
            <PlugZap className="h-5 w-5" />
            Guided MCP Setup
          </h2>
          <p className="mt-2 text-sm leading-6 text-text-muted">
            Add one or more MCP servers, mostly by entering URLs and provider variables. The walkthrough turns remote endpoints into the stdio launcher format this runtime already understands, then saves everything straight into .env.
          </p>
        </div>
        <div className="flex flex-wrap gap-2 text-[11px] uppercase tracking-[0.18em] text-text-muted">
          <span className={`rounded-full px-3 py-2 ${overview?.enabled ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-900"}`}>
            MCP {overview?.enabled ? "enabled" : "disabled"}
          </span>
          <span
            className={`rounded-full px-3 py-2 ${
              overview?.external_integrations_enabled ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-900"
            }`}
          >
            subprocess {overview?.external_integrations_enabled ? "enabled" : "disabled"}
          </span>
          <span className={`rounded-full px-3 py-2 ${overview?.configured ? "bg-surface-container text-primary" : "bg-background text-text-muted"}`}>
            {overview?.configured ? "runtime sees config" : "no active server config"}
          </span>
        </div>
      </div>

      <div className="mt-space-md grid gap-space-md xl:grid-cols-[minmax(0,1.35fr)_minmax(0,0.95fr)]">
        <div className="space-y-space-md">
          <StepCard
            step="01"
            title="Turn on the two global switches"
            description="Every MCP setup needs the feature flag and subprocess integrations. The generated config always includes both switches, and Apply writes them into .env for you."
          >
            <div className="grid gap-space-sm md:grid-cols-2">
              <div className="rounded-xl border border-border-subtle bg-surface-container p-space-sm">
                <div className="font-mono text-sm text-primary">MCP_ENABLED=true</div>
                <p className="mt-2 text-sm leading-6 text-text-muted">Enables MCP server loading and discovery.</p>
              </div>
              <div className="rounded-xl border border-border-subtle bg-surface-container p-space-sm">
                <div className="font-mono text-sm text-primary">EXTERNAL_SUBPROCESS_INTEGRATIONS_ENABLED=true</div>
                <p className="mt-2 text-sm leading-6 text-text-muted">Allows the runtime to launch external MCP processes.</p>
              </div>
            </div>
            <p className={`mt-3 rounded-xl px-3 py-2 text-sm leading-6 ${runtimeFlagsEnabled ? "bg-emerald-50 text-emerald-800" : "bg-amber-50 text-amber-900"}`}>
              {runtimeFlagsEnabled
                ? "The live runtime already has both switches on. You only need to define the server list below."
                : "The live runtime still needs one or both switches. Apply will write them into .env and refresh the MCP runtime in-process."}
            </p>
          </StepCard>

          <StepCard
            step="02"
            title="Add your servers"
            description="Use Remote URL when your provider gives you an MCP endpoint. Switch to Custom stdio only for advanced cases where you already know the executable and args."
          >
            <div className="flex items-center justify-between gap-space-sm">
              <div className="text-sm leading-6 text-text-muted">
                Start with one server. Add more only when you need multiple MCP providers or a fallback setup.
              </div>
              <button
                type="button"
                onClick={addServer}
                className="inline-flex items-center gap-2 rounded-full border border-border-subtle px-4 py-2 text-sm text-text-muted transition hover:bg-surface-container-low hover:text-primary"
              >
                <Plus className="h-4 w-4" />
                Add server
              </button>
            </div>

            <div className="mt-space-md space-y-space-md">
              {serverDrafts.map((draft, index) => {
                const normalized = normalizedDrafts[index];
                const isRemote = draft.mode === "remote";
                return (
                  <article key={draft.id} className="rounded-xl border border-border-subtle bg-background p-space-md">
                    <div className="flex flex-col gap-space-sm border-b border-border-subtle pb-space-sm md:flex-row md:items-center md:justify-between">
                      <div>
                        <div className="text-xs uppercase tracking-[0.18em] text-accent">Server {index + 1}</div>
                        <h3 className="mt-2 text-base font-semibold text-primary">{draft.name.trim() || `server-${index + 1}`}</h3>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded-full bg-surface-container px-3 py-2 text-[11px] uppercase tracking-[0.18em] text-text-muted">
                          {isRemote ? "Remote URL" : "Custom stdio"}
                        </span>
                        <button
                          type="button"
                          onClick={() => removeServer(draft.id)}
                          disabled={serverDrafts.length === 1}
                          className="inline-flex items-center gap-2 rounded-full border border-border-subtle px-4 py-2 text-sm text-text-muted transition hover:bg-surface-container-low hover:text-primary disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          <Trash2 className="h-4 w-4" />
                          Remove
                        </button>
                      </div>
                    </div>

                    <div className="mt-space-md flex flex-wrap gap-2">
                      {[
                        { id: "remote", label: "Remote URL", icon: Link2 },
                        { id: "stdio", label: "Custom stdio", icon: TerminalSquare },
                      ].map((option) => {
                        const Icon = option.icon;
                        const selected = draft.mode === option.id;
                        return (
                          <button
                            key={option.id}
                            type="button"
                            onClick={() => updateDraft(draft.id, { mode: option.id as SetupMode })}
                            className={`inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm transition ${
                              selected
                                ? "border-primary bg-primary text-white"
                                : "border-border-subtle bg-background text-text-muted hover:text-primary"
                            }`}
                          >
                            <Icon className="h-4 w-4" />
                            {option.label}
                          </button>
                        );
                      })}
                    </div>

                    <div className="mt-space-md grid gap-space-md md:grid-cols-2">
                      <label className="block text-sm font-medium text-primary">
                        Server name
                        <input
                          value={draft.name}
                          onChange={(event) => updateDraft(draft.id, { name: event.target.value })}
                          className={fieldClassName}
                          placeholder="archive"
                        />
                      </label>

                      <label className="block text-sm font-medium text-primary">
                        Tool prefix
                        <input
                          value={draft.toolPrefix}
                          onChange={(event) => updateDraft(draft.id, { toolPrefix: event.target.value })}
                          className={fieldClassName}
                          placeholder="mcp"
                        />
                      </label>
                    </div>

                    {isRemote ? (
                      <div className="mt-space-md grid gap-space-md md:grid-cols-[minmax(0,1.2fr)_minmax(220px,0.8fr)]">
                        <label className="block text-sm font-medium text-primary">
                          MCP server URL
                          <input
                            value={draft.serverUrl}
                            onChange={(event) => updateDraft(draft.id, { serverUrl: event.target.value })}
                            className={fieldClassName}
                            placeholder="https://your-mcp-server.example.com/mcp"
                          />
                        </label>

                        <label className="block text-sm font-medium text-primary">
                          Remote bridge preset
                          <select
                            value={draft.remoteLauncher}
                            onChange={(event) => updateDraft(draft.id, { remoteLauncher: event.target.value as RemoteLauncher })}
                            className={fieldClassName}
                          >
                            <option value="npx">npx mcp-remote</option>
                            <option value="uvx">uvx mcp-remote</option>
                          </select>
                        </label>
                      </div>
                    ) : (
                      <div className="mt-space-md grid gap-space-md md:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
                        <label className="block text-sm font-medium text-primary">
                          Command
                          <input
                            value={draft.stdioCommand}
                            onChange={(event) => updateDraft(draft.id, { stdioCommand: event.target.value })}
                            className={fieldClassName}
                            placeholder="python"
                          />
                        </label>

                        <label className="block text-sm font-medium text-primary">
                          Arguments, one per line
                          <textarea
                            value={draft.stdioArgs}
                            onChange={(event) => updateDraft(draft.id, { stdioArgs: event.target.value })}
                            className={textareaClassName}
                            placeholder="-m\narchive_mcp"
                          />
                        </label>
                      </div>
                    )}

                    <div className="mt-space-md grid gap-space-md md:grid-cols-[minmax(0,1fr)_minmax(240px,0.8fr)]">
                      <label className="block text-sm font-medium text-primary">
                        Variables
                        <textarea
                          value={draft.variableLines}
                          onChange={(event) => updateDraft(draft.id, { variableLines: event.target.value })}
                          className={`${textareaClassName} min-h-[140px]`}
                          placeholder="API_KEY=demo-token\nWORKSPACE_ID=alpha"
                        />
                      </label>

                      <label className="block text-sm font-medium text-primary">
                        Working directory (optional)
                        <input
                          value={draft.workingDirectory}
                          onChange={(event) => updateDraft(draft.id, { workingDirectory: event.target.value })}
                          className={fieldClassName}
                          placeholder="./tools/mcp"
                        />
                        <p className="mt-2 text-sm leading-6 text-text-muted">
                          Leave this empty unless the command must start from a specific folder.
                        </p>
                      </label>
                    </div>

                    <div className="mt-space-md grid gap-space-sm lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                      <div className="rounded-xl border border-border-subtle bg-surface-container p-space-sm">
                        <div className="text-xs uppercase tracking-[0.18em] text-text-muted">Launcher preview</div>
                        <p className="mt-2 font-mono text-sm leading-6 text-primary">{normalized.launcherPreview}</p>
                      </div>
                      <div className="rounded-xl border border-border-subtle bg-surface-container p-space-sm">
                        <div className="text-xs uppercase tracking-[0.18em] text-text-muted">Variables summary</div>
                        <p className="mt-2 text-sm leading-6 text-text-muted">
                          {Object.keys(normalized.server.env).length
                            ? `${Object.keys(normalized.server.env).length} variable(s) will be passed to this server.`
                            : "No extra variables yet. Add only the values your provider requires."}
                        </p>
                      </div>
                    </div>

                    {normalized.missingPrimaryInput ? (
                      <p className="mt-3 rounded-xl bg-amber-50 px-3 py-2 text-sm leading-6 text-amber-900">
                        {isRemote ? "Enter the MCP server URL to finish this server." : "Enter the stdio command to finish this server."}
                      </p>
                    ) : null}
                    {normalized.invalidLines.length ? (
                      <p className="mt-3 rounded-xl bg-amber-50 px-3 py-2 text-sm leading-6 text-amber-900">
                        Skipped {normalized.invalidLines.length} malformed variable line(s). Use KEY=value.
                      </p>
                    ) : null}
                  </article>
                );
              })}
            </div>
          </StepCard>

          <StepCard
            step="03"
            title="Choose the env format you want to save"
            description="Use the simple single-server keys when you only have one server. For multiple servers, choose indexed variables or a single MCP_SERVERS_JSON entry."
          >
            <div className="grid gap-space-sm md:grid-cols-3">
              {[
                {
                  id: "single",
                  label: "Simple single-server",
                  description: "Writes MCP_SERVER_* keys. Best for one server only.",
                  disabled: serverDrafts.length !== 1,
                },
                {
                  id: "indexed",
                  label: "Indexed variables",
                  description: "Writes MCP_SERVER_1_* and MCP_SERVER_2_* style keys.",
                  disabled: false,
                },
                {
                  id: "json",
                  label: "MCP_SERVERS_JSON",
                  description: "Stores the entire server list in one compact JSON value.",
                  disabled: false,
                },
              ].map((option) => {
                const selected = configFormat === option.id;
                return (
                  <button
                    key={option.id}
                    type="button"
                    disabled={option.disabled}
                    onClick={() => setConfigFormat(option.id as MCPConfigurationFormat)}
                    className={`rounded-xl border p-space-md text-left transition ${
                      selected
                        ? "border-primary bg-primary text-white"
                        : "border-border-subtle bg-background text-text-muted hover:border-primary hover:text-primary"
                    } disabled:cursor-not-allowed disabled:opacity-50`}
                  >
                    <div className="text-sm font-semibold">{option.label}</div>
                    <p className={`mt-2 text-sm leading-6 ${selected ? "text-white/85" : "text-text-muted"}`}>{option.description}</p>
                  </button>
                );
              })}
            </div>

            <div className="mt-space-md grid gap-space-sm md:grid-cols-3">
              <div className="rounded-xl border border-border-subtle bg-surface-container p-space-sm">
                <div className="text-xs uppercase tracking-[0.18em] text-text-muted">Server count</div>
                <p className="mt-2 text-sm font-semibold text-primary">{serverDrafts.length}</p>
              </div>
              <div className="rounded-xl border border-border-subtle bg-surface-container p-space-sm">
                <div className="text-xs uppercase tracking-[0.18em] text-text-muted">Selected format</div>
                <p className="mt-2 text-sm font-semibold text-primary">{formatBadgeLabel(configFormat)}</p>
              </div>
              <div className="rounded-xl border border-border-subtle bg-surface-container p-space-sm">
                <div className="text-xs uppercase tracking-[0.18em] text-text-muted">Blocking issues</div>
                <p className="mt-2 text-sm font-semibold text-primary">{invalidLineCount + missingPrimaryCount}</p>
              </div>
            </div>

            {serverDrafts.length > 1 && configFormat === "indexed" ? (
              <p className="mt-3 rounded-xl bg-surface-container px-3 py-2 text-sm leading-6 text-text-muted">
                Indexed format is active because you now have more than one server. Switch to MCP_SERVERS_JSON if you prefer a single compact assignment.
              </p>
            ) : null}
          </StepCard>
        </div>

        <aside className="rounded-xl border border-border-subtle bg-background p-space-md">
          <div className="flex items-start justify-between gap-space-md border-b border-border-subtle pb-space-sm">
            <div>
              <div className="text-xs uppercase tracking-[0.18em] text-accent">Step 04</div>
              <h3 className="mt-2 flex items-center gap-space-sm text-base font-semibold text-primary">
                <Server className="h-4 w-4" />
                Review And Apply
              </h3>
              <p className="mt-2 text-sm leading-6 text-text-muted">
                Copy the generated block if you want it, or apply it directly. The backend saves the block into the repo root .env and rebuilds the live MCP runtime so discovery can run immediately.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => void handleCopyConfig()}
                disabled={copyDisabled}
                className="inline-flex items-center gap-2 rounded-full border border-border-subtle px-4 py-2 text-sm text-text-muted transition hover:bg-surface-container-low hover:text-primary disabled:cursor-not-allowed disabled:opacity-60"
              >
                <Copy className="h-4 w-4" />
                {copyState === "copied" ? "Copied" : copyState === "error" ? "Copy failed" : "Copy block"}
              </button>
              <button
                type="button"
                onClick={() => void handleApplyConfig()}
                disabled={hasBlockingErrors || isApplyingMcp}
                className="inline-flex items-center gap-2 rounded-full border border-primary bg-primary px-4 py-2 text-sm text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <Save className="h-4 w-4" />
                {isApplyingMcp ? "Applying" : "Apply to .env"}
              </button>
            </div>
          </div>

          <pre className="mt-space-md overflow-x-auto rounded-xl bg-surface-container p-space-md text-xs leading-6 text-primary">
            <code>{envBlock}</code>
          </pre>

          {hasBlockingErrors ? (
            <p className="mt-3 rounded-xl bg-amber-50 px-3 py-2 text-sm leading-6 text-amber-900">
              Resolve {missingPrimaryCount} missing launcher field(s) and {invalidLineCount} malformed variable line(s) before applying this configuration.
            </p>
          ) : null}
          {applyState.tone !== "idle" ? (
            <p
              className={`mt-3 rounded-xl px-3 py-2 text-sm leading-6 ${
                applyState.tone === "success" ? "bg-emerald-50 text-emerald-800" : "bg-red-50 text-red-900"
              }`}
            >
              {applyState.message}
            </p>
          ) : null}

          <div className="mt-space-md grid gap-space-sm">
            <div className="rounded-xl border border-border-subtle bg-surface-container p-space-sm">
              <div className="text-xs uppercase tracking-[0.18em] text-text-muted">Config summary</div>
              <p className="mt-2 text-sm leading-6 text-primary">
                {serverDrafts.length} server(s), {formatBadgeLabel(configFormat)}, {normalizedDrafts.reduce((total, draft) => total + Object.keys(draft.server.env).length, 0)} total variable(s)
              </p>
            </div>
            <div className="rounded-xl border border-border-subtle bg-surface-container p-space-sm">
              <div className="text-xs uppercase tracking-[0.18em] text-text-muted">What Apply does</div>
              <ul className="mt-2 space-y-2 text-sm leading-6 text-text-muted">
                <li>Replaces older MCP-related keys in the repo root .env file.</li>
                <li>Updates the live backend process with the same values.</li>
                <li>Leaves the current format visible here so you can still copy it elsewhere.</li>
              </ul>
            </div>
            {lastApplyResponse ? (
              <div className="rounded-xl border border-border-subtle bg-surface-container p-space-sm">
                <div className="text-xs uppercase tracking-[0.18em] text-text-muted">Last apply result</div>
                <p className="mt-2 text-sm leading-6 text-text-muted">
                  Saved {lastApplyResponse.server_count} server(s) to {lastApplyResponse.env_path} using {formatBadgeLabel(lastApplyResponse.format)}.
                </p>
              </div>
            ) : null}
          </div>

          <div className="mt-space-md flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={() => void onRefreshMcp()}
              disabled={isRefreshingMcp}
              className="inline-flex items-center gap-2 rounded-full border border-border-subtle px-4 py-2 text-sm text-text-muted transition hover:bg-surface-container-low hover:text-primary disabled:cursor-not-allowed disabled:opacity-60"
            >
              <RefreshCw className={`h-4 w-4 ${isRefreshingMcp ? "animate-spin" : ""}`} />
              {isRefreshingMcp ? "Refreshing" : "Refresh MCP discovery"}
            </button>
            <p className="text-sm leading-6 text-text-muted">
              After Apply, use Refresh MCP to confirm the live runtime can discover tools from the saved server list.
            </p>
          </div>
        </aside>
      </div>
    </article>
  );
}