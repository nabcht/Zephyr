import {
  Activity,
  BookOpen,
  CircleUserRound,
  Command,
  FileCode2,
  HelpCircle,
  LockKeyhole,
  MessageSquare,
  Settings,
  Shield,
  type LucideIcon,
} from "lucide-react";
import type { ReactNode } from "react";

import type { AppView } from "../components/AppShell";
import { WorkspaceHeader } from "../components/WorkspaceHeader";
import type { SystemStatus } from "../types/api";

interface NavigationPageProps {
  status: SystemStatus | null;
  sessionId: string | null;
  onNavigate: (view: AppView) => void;
}

interface PageSectionProps {
  eyebrow?: string;
  title: string;
  description?: string;
  children: ReactNode;
}

interface KeyValueItem {
  label: string;
  value: string;
}

function PageSection({ eyebrow, title, description, children }: PageSectionProps) {
  return (
    <section className="rounded-xl border border-border-subtle bg-surface p-space-md shadow-sm">
      {eyebrow ? <div className="font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted">{eyebrow}</div> : null}
      <h2 className="mt-1 text-xl font-semibold text-primary">{title}</h2>
      {description ? <p className="mt-2 text-sm leading-6 text-text-muted">{description}</p> : null}
      <div className="mt-space-md">{children}</div>
    </section>
  );
}

function ActionLink({
  label,
  view,
  onNavigate,
  icon: Icon,
}: {
  label: string;
  view: AppView;
  onNavigate: (view: AppView) => void;
  icon: LucideIcon;
}) {
  return (
    <button
      type="button"
      onClick={() => onNavigate(view)}
      className="inline-flex items-center gap-space-sm rounded-lg border border-border-subtle px-space-md py-space-sm text-sm font-medium text-primary transition hover:bg-surface-container-low"
    >
      <Icon className="h-4 w-4" />
      {label}
    </button>
  );
}

function BulletList({ items }: { items: string[] }) {
  return (
    <ul className="space-y-3 text-sm leading-6 text-text-muted">
      {items.map((item) => (
        <li key={item} className="flex gap-space-sm">
          <span className="mt-2 h-1.5 w-1.5 rounded-full bg-secondary" />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

function KeyValueGrid({ items }: { items: KeyValueItem[] }) {
  return (
    <div className="grid gap-space-sm sm:grid-cols-2">
      {items.map((item) => (
        <article key={item.label} className="rounded-lg border border-border-subtle bg-surface-container-lowest p-space-sm">
          <div className="font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted">{item.label}</div>
          <div className="mt-2 text-sm font-medium text-primary">{item.value}</div>
        </article>
      ))}
    </div>
  );
}

function Table({ rows }: { rows: Array<[string, string, string]> }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border-subtle">
      <table className="min-w-full divide-y divide-border-subtle text-sm">
        <thead className="bg-surface-container-lowest">
          <tr className="font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted">
            <th className="px-space-sm py-space-sm text-left font-medium">Setting</th>
            <th className="px-space-sm py-space-sm text-left font-medium">Purpose</th>
            <th className="px-space-sm py-space-sm text-left font-medium">Default</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border-subtle bg-surface">
          {rows.map(([setting, purpose, fallback]) => (
            <tr key={setting}>
              <td className="px-space-sm py-space-sm font-mono text-xs text-primary">{setting}</td>
              <td className="px-space-sm py-space-sm text-text-muted">{purpose}</td>
              <td className="px-space-sm py-space-sm text-text-muted">{fallback}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function readOnlyStatusValue(value: string | number | boolean | null | undefined): string {
  if (value === null || value === undefined || value === "") {
    return "Unavailable";
  }
  if (typeof value === "boolean") {
    return value ? "Enabled" : "Disabled";
  }
  return String(value);
}

export function DocsPage({ onNavigate }: NavigationPageProps) {
  return (
    <div className="space-y-6">
      <WorkspaceHeader
        eyebrow="Docs"
        title="uZephyr Features & Architecture"
        subtitle="A deeper tour of the hybrid control room, FastAPI bridge, and local-first runtime that power day-to-day operator workflows."
        icon={BookOpen}
        actions={
          <>
            <ActionLink label="API Docs" view="api-docs" onNavigate={onNavigate} icon={FileCode2} />
            <ActionLink label="Privacy" view="privacy" onNavigate={onNavigate} icon={LockKeyhole} />
          </>
        }
      />

      <PageSection
        eyebrow="Core"
        title="Feature Set"
        description="uZephyr is built for agency rather than one-shot chatting. The current hybrid stack combines persistent memory, autonomous workflows, modular tools, and operator-visible safety controls."
      >
        <div className="grid gap-space-md lg:grid-cols-2">
          <article className="rounded-lg border border-border-subtle bg-surface-container-lowest p-space-md">
            <h3 className="text-base font-semibold text-primary">Hybrid Memory</h3>
            <BulletList
              items={[
                "Session history is persisted in the local SQLite runtime store so web and CLI turns can restore recent context.",
                "Semantic and keyword search use the local vector store and keyword index under the data directory for search-backed retrieval.",
                "The knowledge brain under knowledge/brain remains the durable place for project facts, truth notes, and persona context.",
              ]}
            />
          </article>

          <article className="rounded-lg border border-border-subtle bg-surface-container-lowest p-space-md">
            <h3 className="text-base font-semibold text-primary">Autonomous Missions</h3>
            <BulletList
              items={[
                "Mission turns are objective-driven and run through the same shared runtime used by standard chat.",
                "The hybrid UI streams mission progress snapshots so operators can inspect milestones before the final persisted answer lands.",
                "Browser verification remains bounded, while the CLI /verify path is still the full fallback for heavier regression work.",
              ]}
            />
          </article>

          <article className="rounded-lg border border-border-subtle bg-surface-container-lowest p-space-md">
            <h3 className="text-base font-semibold text-primary">Skills & MCP</h3>
            <BulletList
              items={[
                "Native Python skills live under skills/ and are hot-reloadable through the shared runtime reload path.",
                "MCP inventory, discovery freshness, degraded reasons, and recent execution results surface in the command center.",
                "Reloading tools updates the shared backend services rather than rebuilding separate web-only logic.",
              ]}
            />
          </article>

          <article className="rounded-lg border border-border-subtle bg-surface-container-lowest p-space-md">
            <h3 className="text-base font-semibold text-primary">Privacy & Safety</h3>
            <BulletList
              items={[
                "Ollama and LlamaCPP keep inference local, while OpenRouter is surfaced clearly as a remote-capable provider.",
                "Safety confirmation can remain in the loop for sensitive tool execution when REQUIRE_CONFIRMATION is enabled.",
                "The Posture and Activity views expose privacy boundaries, runtime trust, readiness state, and current operational constraints in one place.",
              ]}
            />
          </article>
        </div>
      </PageSection>

      <PageSection
        eyebrow="Architecture"
        title="Three-Layer Runtime"
        description="The hybrid app is intentionally split so the UI stays responsive while Python keeps ownership of execution, persistence, tools, and validation."
      >
        <div className="grid gap-space-md lg:grid-cols-3">
          <article className="rounded-lg border border-border-subtle bg-surface-container-lowest p-space-md">
            <h3 className="text-base font-semibold text-primary">Control Room</h3>
            <BulletList
              items={[
                "React + Vite frontend with router-driven paths for Chat, Command Center, Posture, Activity, and the shell documentation pages.",
                "Consumes REST snapshots plus Server-Sent Events for chat, missions, reload, and prepare actions.",
                "Serves as the primary operator surface while the terminal remains the explicit fallback path.",
              ]}
            />
          </article>

          <article className="rounded-lg border border-border-subtle bg-surface-container-lowest p-space-md">
            <h3 className="text-base font-semibold text-primary">Bridge</h3>
            <BulletList
              items={[
                "FastAPI backend exposes system, runtime, session, chat, mission, and command-center endpoints over the shared runtime.",
                "Session restore and passive status snapshots avoid forcing heavy runtime boot when a lightweight answer is enough.",
                "Runtime services own streaming responses, preparation flows, and verification orchestration for the browser. ",
              ]}
            />
          </article>

          <article className="rounded-lg border border-border-subtle bg-surface-container-lowest p-space-md">
            <h3 className="text-base font-semibold text-primary">Core Runtime</h3>
            <BulletList
              items={[
                "AppRuntime owns memory, tools, LLM routing, background warm-up, and post-turn deferred search refresh scheduling.",
                "LLMRouter tracks provider readiness plus recent warm-up and live-call timings for operational visibility.",
                "Chat, missions, tool execution, and MCP integration all run through the same Python-owned execution layer.",
              ]}
            />
          </article>
        </div>
      </PageSection>

      <PageSection
        eyebrow="Workflows"
        title="Advanced Use"
        description="The most useful extension and ingestion paths stay local and repo-driven."
      >
        <div className="grid gap-space-md lg:grid-cols-2">
          <article className="rounded-lg border border-border-subtle bg-surface-container-lowest p-space-md">
            <h3 className="text-base font-semibold text-primary">Create a Skill</h3>
            <BulletList
              items={[
                "Add a Python skill under skills/ using the existing module pattern and a clear docstring or function description.",
                "Use Reload tools from the shell or the runtime reload path to make the new capability available without restarting the full stack.",
                "Prefer import-safe skill modules so missing optional dependencies degrade cleanly instead of polluting the tool inventory.",
              ]}
            />
          </article>

          <article className="rounded-lg border border-border-subtle bg-surface-container-lowest p-space-md">
            <h3 className="text-base font-semibold text-primary">Knowledge & Search</h3>
            <BulletList
              items={[
                "Place markdown or other supported content under the workspace and knowledge directories you want the search runtime to index.",
                "Use Prepare Runtime when local model assets or search warm-up still need to settle.",
                "The shared retriever combines semantic and keyword results instead of falling back to a UI-only search path.",
              ]}
            />
          </article>
        </div>
      </PageSection>

      <PageSection eyebrow="Config" title="Common Environment Settings">
        <Table
          rows={[
            ["LLM_PROVIDER", "Select the active inference backend.", "ollama"],
            ["REQUIRE_CONFIRMATION", "Require browser approval before sensitive tool execution.", "false"],
            ["MCP_ENABLED", "Enable MCP server configuration and discovery.", "false"],
            ["EXTERNAL_SUBPROCESS_INTEGRATIONS_ENABLED", "Allow optional subprocess-backed integrations.", "false"],
            ["DB_PATH", "Location of the local SQLite runtime database.", "./data/zephyr.db"],
            ["VECTOR_STORE_DIR", "Location of the local semantic vector store.", "./data/vector_store"],
          ]}
        />
      </PageSection>

      <PageSection eyebrow="Requirements" title="System Baseline">
        <BulletList
          items={[
            "Python 3.10+ for the shared backend runtime and async-first services.",
            "Node.js 18+ for the React control room and frontend build pipeline.",
            "Enough local RAM and storage for your selected inference provider, runtime assets, and vector/search indexes.",
          ]}
        />
      </PageSection>
    </div>
  );
}

export function SupportPage({ status, sessionId, onNavigate }: NavigationPageProps) {
  return (
    <div className="space-y-6">
      <WorkspaceHeader
        eyebrow="Support"
        title="Operator Support"
        subtitle="Recovery guidance and quick links for the parts of the hybrid stack that most often need operator attention."
        icon={HelpCircle}
      />

      <PageSection
        eyebrow="Fast Path"
        title="Start Here"
        description="The shell chrome now routes to real pages, but most runtime issues are still best triaged through the main operator surfaces below."
      >
        <div className="flex flex-wrap gap-space-sm">
          <ActionLink label="Open Command Center" view="command-center" onNavigate={onNavigate} icon={Command} />
          <ActionLink label="Open Activity" view="activity" onNavigate={onNavigate} icon={Activity} />
          <ActionLink label="Read Docs" view="docs" onNavigate={onNavigate} icon={BookOpen} />
          <ActionLink label="Open API Docs" view="api-docs" onNavigate={onNavigate} icon={FileCode2} />
        </div>
      </PageSection>

      <PageSection
        eyebrow="Recovery"
        title="Common Workflows"
        description="These are the current operator-first paths for keeping the hybrid app healthy during everyday use."
      >
        <BulletList
          items={[
            "Use Verify Runtime from Command Center for the browser-safe diagnostic pass, and fall back to the CLI /verify workflow for the full regression run when mission evals need more than the browser timeout window.",
            "Use Reload tools after skill edits or MCP configuration changes that should update runtime inventory without restarting the backend process.",
            "Use Prepare Runtime when local model assets, provider warm-up, or search readiness still need to settle before the next heavy turn.",
            "Check the Activity page for provider warm-up timings, last provider-call duration, search readiness, and current runtime action output before assuming the browser is stuck.",
          ]}
        />
      </PageSection>

      <PageSection eyebrow="Snapshot" title="Current Runtime View">
        <KeyValueGrid
          items={[
            { label: "Session", value: readOnlyStatusValue(sessionId ?? "No session") },
            { label: "Provider", value: readOnlyStatusValue(status?.provider) },
            { label: "Inference", value: readOnlyStatusValue(status?.inference_status) },
            { label: "Search", value: readOnlyStatusValue(status?.search_status) },
            { label: "Verification Gate", value: readOnlyStatusValue(status?.safety_confirmation_required) },
            { label: "External Integrations", value: readOnlyStatusValue(status?.external_integrations_enabled) },
          ]}
        />
      </PageSection>
    </div>
  );
}

export function SettingsPage({ status }: NavigationPageProps) {
  return (
    <div className="space-y-6">
      <WorkspaceHeader
        eyebrow="Settings"
        title="Runtime Settings"
        subtitle="A read-only summary of the current hybrid configuration. Runtime settings are still environment-driven rather than browser-editable."
        icon={Settings}
      />

      <PageSection eyebrow="Current" title="Active Configuration">
        <KeyValueGrid
          items={[
            { label: "Provider", value: readOnlyStatusValue(status?.provider) },
            { label: "Model", value: readOnlyStatusValue(status?.model) },
            { label: "Safety Confirmation", value: readOnlyStatusValue(status?.safety_confirmation_required) },
            { label: "External Integrations", value: readOnlyStatusValue(status?.external_integrations_enabled) },
            { label: "Interfaces", value: readOnlyStatusValue(status?.interfaces.join(", ")) },
            { label: "Design System", value: readOnlyStatusValue(status?.design_system_path) },
          ]}
        />
      </PageSection>

      <PageSection
        eyebrow="Prepare"
        title="Prepare-Capable Actions"
        description="These browser-visible actions currently advertise that they can settle local runtime prerequisites."
      >
        <BulletList
          items={status?.prepare_actions.length ? status.prepare_actions : ["No prepare-capable startup actions are currently advertised by the runtime."]}
        />
      </PageSection>

      <PageSection
        eyebrow="Edit Outside Browser"
        title="Environment-Driven Knobs"
        description="The current shell shows these values but does not yet edit them in place."
      >
        <Table
          rows={[
            ["LLM_PROVIDER", "Switch between ollama, openrouter, and llamacpp.", "ollama"],
            ["REQUIRE_CONFIRMATION", "Control sensitive-tool approval behavior.", "false"],
            ["MCP_ENABLED", "Enable MCP configuration and discovery.", "false"],
            ["OPENROUTER_MODEL", "Choose the active OpenRouter model when that provider is enabled.", "openai/gpt-oss-120b:free"],
            ["VECTOR_STORE_DIR", "Move the semantic vector store to another local path.", "./data/vector_store"],
            ["DB_PATH", "Move the local runtime SQLite database.", "./data/zephyr.db"],
          ]}
        />
      </PageSection>
    </div>
  );
}

export function ProfilePage({ status, sessionId, onNavigate }: NavigationPageProps) {
  return (
    <div className="space-y-6">
      <WorkspaceHeader
        eyebrow="Profile"
        title="Local Operator Profile"
        subtitle="uZephyr currently treats the browser user as a local operator rather than a network-authenticated account. This page summarizes the active local session."
        icon={CircleUserRound}
      />

      <PageSection eyebrow="Identity" title="Session Snapshot">
        <KeyValueGrid
          items={[
            { label: "Session ID", value: readOnlyStatusValue(sessionId ?? "No active chat session") },
            { label: "Runtime State", value: readOnlyStatusValue(status?.runtime_initialized ? "Ready" : "Starting") },
            { label: "Loaded Tools", value: readOnlyStatusValue(status?.tool_counts.total) },
            { label: "Remote Capabilities", value: readOnlyStatusValue(status?.privacy_status.remote_capabilities.length) },
            { label: "Privacy Badge", value: readOnlyStatusValue(status?.privacy_status.badge) },
            { label: "Trust Title", value: readOnlyStatusValue(status?.trust_status.title) },
          ]}
        />
      </PageSection>

      <PageSection
        eyebrow="Model"
        title="What This Profile Means"
        description="The current hybrid shell does not maintain a cloud user account, profile preferences store, or remote identity service. The operator profile is the local workspace plus the active runtime state."
      >
        <BulletList
          items={[
            "Session history and durable memory are local runtime concerns, not a hosted account feature.",
            "Provider choice, safety gates, and MCP enablement are configuration concerns driven by the environment and workspace state.",
            "If you need to inspect privacy boundaries or runtime trust signals, the Posture page is the right operational surface.",
          ]}
        />
        <div className="mt-space-md flex flex-wrap gap-space-sm">
          <ActionLink label="Return to Chat" view="chat" onNavigate={onNavigate} icon={MessageSquare} />
          <ActionLink label="Open Posture" view="posture" onNavigate={onNavigate} icon={Shield} />
        </div>
      </PageSection>
    </div>
  );
}

export function TermsPage({ onNavigate }: NavigationPageProps) {
  return (
    <div className="space-y-6">
      <WorkspaceHeader
        eyebrow="Terms"
        title="Terms of Service"
        subtitle="Updated May 18, 2026. These terms focus on user responsibility for a self-hosted, local-first operator tool."
        icon={Shield}
        actions={<ActionLink label="Privacy Policy" view="privacy" onNavigate={onNavigate} icon={LockKeyhole} />}
      />

      <PageSection title="Use of Software">
        <BulletList
          items={[
            "uZephyr is provided as an open-source tool for personal and professional use.",
            "You are responsible for the environment in which it is deployed and the data it can access.",
          ]}
        />
      </PageSection>

      <PageSection title="AI Output Disclaimer">
        <BulletList
          items={[
            "uZephyr can interface with local or remote LLM providers.",
            "Generated content, tool plans, and autonomous mission outputs are not guaranteed to be accurate, safe, or reliable without operator review.",
          ]}
        />
      </PageSection>

      <PageSection title="Responsibility for Actions">
        <BulletList
          items={[
            "If REQUIRE_CONFIRMATION is disabled, the runtime may execute local file, shell, or integration-backed actions without an extra approval click.",
            "You accept responsibility for any data loss, system damage, or unintended side effects that result from the way the software is configured and used.",
          ]}
        />
      </PageSection>

      <PageSection title="Limitation of Liability">
        <BulletList
          items={[
            "The software is provided as-is without warranty of any kind.",
            "In no event shall the authors or contributors be liable for claims, damages, or other liability arising from use of the software.",
          ]}
        />
      </PageSection>

      <PageSection title="License">
        <p className="text-sm leading-6 text-text-muted">Usage remains governed by the MIT License included in this repository.</p>
      </PageSection>
    </div>
  );
}

export function PrivacyPage({ status, onNavigate }: NavigationPageProps) {
  return (
    <div className="space-y-6">
      <WorkspaceHeader
        eyebrow="Privacy"
        title="Privacy Policy"
        subtitle="uZephyr is built with a local-first posture. This page summarizes what stays on your machine and what can leave it depending on provider and integration settings."
        icon={LockKeyhole}
        actions={<ActionLink label="Terms" view="terms" onNavigate={onNavigate} icon={Shield} />}
      />

      <PageSection title="Data Residency">
        <BulletList
          items={[
            "Chat history, vector indexes, keyword indexes, logs, and durable knowledge files are stored in local workspace-controlled paths by default.",
            "The current repo does not include built-in telemetry or third-party analytics in the hybrid operator surface.",
          ]}
        />
      </PageSection>

      <PageSection title="Third-Party Providers">
        <BulletList
          items={[
            "Ollama and LlamaCPP keep inference local to your machine.",
            "When OpenRouter is enabled, prompts and tool context can be sent to that remote provider according to your configuration.",
            "Optional MCP and subprocess-backed integrations can also extend the runtime beyond the local machine when explicitly enabled.",
          ]}
        />
      </PageSection>

      <PageSection title="Live Privacy Posture">
        <KeyValueGrid
          items={[
            { label: "Current Backend", value: readOnlyStatusValue(status?.privacy_status.inference_backend) },
            { label: "Privacy Badge", value: readOnlyStatusValue(status?.privacy_status.badge) },
            { label: "Remote Capabilities", value: readOnlyStatusValue(status?.privacy_status.remote_capabilities.join(", ") || "None surfaced") },
            { label: "Safety Confirmation", value: readOnlyStatusValue(status?.safety_confirmation_required) },
          ]}
        />
      </PageSection>

      <PageSection title="Security Note">
        <p className="text-sm leading-6 text-text-muted">
          The runtime includes sandbox-backed execution paths, but it is still a local operator tool with filesystem and command capabilities. Run it only in environments you trust.
        </p>
      </PageSection>
    </div>
  );
}

export function ApiDocsPage({ onNavigate }: NavigationPageProps) {
  return (
    <div className="space-y-6">
      <WorkspaceHeader
        eyebrow="API"
        title="FastAPI Bridge Reference"
        subtitle="Reference for the current local backend bridge exposed by the hybrid app. Default local base URL: http://127.0.0.1:8000."
        icon={FileCode2}
        actions={<ActionLink label="System Docs" view="docs" onNavigate={onNavigate} icon={BookOpen} />}
      />

      <PageSection title="System Endpoints">
        <BulletList
          items={[
            "GET /api/system/health returns a lightweight backend health response.",
            "GET /api/system/status returns the current runtime snapshot, including provider readiness, inference timings, startup guidance, trust posture, and tool counts.",
          ]}
        />
      </PageSection>

      <PageSection title="Runtime Endpoints">
        <BulletList
          items={[
            "POST /api/runtime/reload reloads tool definitions and refreshes background search state.",
            "POST /api/runtime/reload/stream streams runtime reload progress as Server-Sent Events.",
            "POST /api/runtime/prepare prepares local runtime assets and returns a final preparation payload.",
            "POST /api/runtime/prepare/stream streams preparation progress as Server-Sent Events.",
          ]}
        />
      </PageSection>

      <PageSection title="Sessions, Chat, and Missions">
        <BulletList
          items={[
            "POST /api/sessions creates a web session identifier.",
            "GET /api/sessions/{session_id}/messages returns recent persisted messages for the session.",
            "POST /api/chat/turn accepts { session_id, message, allow_sensitive_tools? } and returns one persisted assistant response.",
            "POST /api/chat/stream accepts the same body and returns Server-Sent Event snapshots plus a final done event.",
            "POST /api/missions/turn and POST /api/missions/stream use the same request body shape for persisted mission execution and mission progress streaming.",
          ]}
        />
      </PageSection>

      <PageSection title="Command Center Endpoints">
        <BulletList
          items={[
            "GET /api/command-center/overview returns CLI-equivalent web inspection data for tools, MCP, memory, and commands.",
            "POST /api/command-center/mcp/refresh refreshes cached MCP discovery without reloading the full runtime.",
            "POST /api/command-center/verify runs the browser-facing runtime verification workflow.",
          ]}
        />
      </PageSection>

      <PageSection title="Authentication & Exposure">
        <p className="text-sm leading-6 text-text-muted">
          The current backend is designed for local-host access and does not ship with a global auth layer. If you expose it beyond the local machine, add your own reverse proxy, VPN, or comparable access control.
        </p>
      </PageSection>
    </div>
  );
}