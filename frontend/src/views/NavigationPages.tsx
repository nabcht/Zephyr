import {
  Activity,
  BookOpen,
  CircleUserRound,
  Command,
  FileCode2,
  HelpCircle,
  LockKeyhole,
  MessageSquare,
  Search,
  Settings,
  Shield,
  type LucideIcon,
} from "lucide-react";
import type { ReactNode } from "react";

import type { AppView } from "../components/AppShell";
import { MarkdownDocumentPage } from "../components/MarkdownDocumentPage";
import { WorkspaceHeader } from "../components/WorkspaceHeader";
import type { SystemStatus } from "../types/api";

interface NavigationPageProps {
  status: SystemStatus | null;
  sessionId: string | null;
  onNavigate: (view: AppView) => void;
}

interface PageSectionProps {
  title: string;
  children: ReactNode;
  eyebrow?: string;
  description?: string;
}

interface ActionLinkProps {
  label: string;
  view: AppView;
  onNavigate: (view: AppView) => void;
  icon: LucideIcon;
}

interface KeyValueItem {
  label: string;
  value: string;
}

function ActionLink({ label, view, onNavigate, icon: Icon }: ActionLinkProps) {
  return (
    <button
      type="button"
      onClick={() => onNavigate(view)}
      className="inline-flex items-center gap-space-sm rounded-lg border border-border-subtle bg-surface px-space-sm py-space-sm text-sm font-medium text-primary transition hover:border-secondary/30 hover:text-secondary"
    >
      <Icon className="h-4 w-4" />
      {label}
    </button>
  );
}

function PageSection({ title, children, eyebrow, description }: PageSectionProps) {
  return (
    <section className="rounded-xl border border-border-subtle bg-surface p-space-lg shadow-sm">
      <div className="space-y-2">
        {eyebrow ? <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-text-muted">{eyebrow}</p> : null}
        <h2 className="text-lg font-semibold text-primary">{title}</h2>
        {description ? <p className="text-sm leading-6 text-text-muted">{description}</p> : null}
      </div>
      <div className="mt-space-md">{children}</div>
    </section>
  );
}

function BulletList({ items }: { items: string[] }) {
  return (
    <ul className="space-y-3 pl-6 text-sm leading-7 text-text-muted">
      {items.map((item) => (
        <li key={item} className="list-disc">
          {item}
        </li>
      ))}
    </ul>
  );
}

function KeyValueGrid({ items }: { items: KeyValueItem[] }) {
  return (
    <div className="grid gap-space-md sm:grid-cols-2 xl:grid-cols-3">
      {items.map((item) => (
        <article key={item.label} className="rounded-lg border border-border-subtle bg-surface-container-lowest p-space-md">
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted">{item.label}</p>
          <p className="mt-2 text-sm font-medium leading-6 text-primary">{item.value}</p>
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
    <MarkdownDocumentPage
      slug="docs"
      eyebrow="Docs"
      fallbackTitle="Zephyr Features & Architecture"
      fallbackSubtitle="Loading the architecture guide from the Docs folder."
      icon={BookOpen}
      actions={
        <>
          <ActionLink label="Features" view="features" onNavigate={onNavigate} icon={BookOpen} />
          <ActionLink label="Glossary" view="glossary" onNavigate={onNavigate} icon={Search} />
          <ActionLink label="API Docs" view="api-docs" onNavigate={onNavigate} icon={FileCode2} />
          <ActionLink label="Privacy" view="privacy" onNavigate={onNavigate} icon={LockKeyhole} />
        </>
      }
    />
  );
}

export function FeaturesPage({ onNavigate }: NavigationPageProps) {
  return (
    <MarkdownDocumentPage
      slug="features"
      eyebrow="Features"
      fallbackTitle="Zephyr Features"
      fallbackSubtitle="Loading the current feature inventory from Docs/Features.md."
      icon={BookOpen}
      actions={
        <>
          <ActionLink label="Architecture" view="docs" onNavigate={onNavigate} icon={BookOpen} />
          <ActionLink label="Glossary" view="glossary" onNavigate={onNavigate} icon={Search} />
          <ActionLink label="API Docs" view="api-docs" onNavigate={onNavigate} icon={FileCode2} />
        </>
      }
    />
  );
}

export function GlossaryPage({ onNavigate }: NavigationPageProps) {
  return (
    <MarkdownDocumentPage
      slug="glossary"
      eyebrow="Glossary"
      fallbackTitle="Zephyr Shared Vocabulary"
      fallbackSubtitle="Loading the glossary directly from Docs/glossary.md."
      icon={Search}
      actions={
        <>
          <ActionLink label="Features" view="features" onNavigate={onNavigate} icon={BookOpen} />
          <ActionLink label="Architecture" view="docs" onNavigate={onNavigate} icon={BookOpen} />
          <ActionLink label="API Docs" view="api-docs" onNavigate={onNavigate} icon={FileCode2} />
        </>
      }
    />
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
          <ActionLink label="Read Docs" view="features" onNavigate={onNavigate} icon={BookOpen} />
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
        subtitle="Zephyr currently treats the browser user as a local operator rather than a network-authenticated account. This page summarizes the active local session."
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
    <MarkdownDocumentPage
      slug="terms"
      eyebrow="Terms"
      fallbackTitle="Terms of Service"
      fallbackSubtitle="Loading the current terms directly from Docs/TERMS.md."
      icon={Shield}
      actions={<ActionLink label="Privacy Policy" view="privacy" onNavigate={onNavigate} icon={LockKeyhole} />}
    />
  );
}

export function PrivacyPage({ status, onNavigate }: NavigationPageProps) {
  return (
    <MarkdownDocumentPage
      slug="privacy"
      eyebrow="Privacy"
      fallbackTitle="Privacy Policy"
      fallbackSubtitle="Loading the privacy policy directly from Docs/PRIVACY.md."
      icon={LockKeyhole}
      actions={<ActionLink label="Terms" view="terms" onNavigate={onNavigate} icon={Shield} />}
    >
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
    </MarkdownDocumentPage>
  );
}

export function ApiDocsPage({ onNavigate }: NavigationPageProps) {
  return (
    <MarkdownDocumentPage
      slug="api-docs"
      eyebrow="API"
      fallbackTitle="FastAPI Bridge Reference"
      fallbackSubtitle="Loading the API reference directly from Docs/API_DOCS.md."
      icon={FileCode2}
      actions={
        <>
          <ActionLink label="Features" view="features" onNavigate={onNavigate} icon={BookOpen} />
          <ActionLink label="System Docs" view="docs" onNavigate={onNavigate} icon={BookOpen} />
        </>
      }
    />
  );
}