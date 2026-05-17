import {
  Activity,
  BookOpen,
  Bot,
  CircleUserRound,
  Command,
  Cpu,
  Fingerprint,
  FolderSync,
  HelpCircle,
  MessageSquare,
  RefreshCw,
  Search,
  Settings,
  Shield,
  type LucideIcon,
} from "lucide-react";
import type { PropsWithChildren } from "react";

import type { SystemStatus } from "../types/api";

export type AppView = "chat" | "command-center" | "posture" | "activity";

interface AppShellProps extends PropsWithChildren {
  activeView: AppView;
  onViewChange: (view: AppView) => void;
  status: SystemStatus | null;
  sessionId: string | null;
  isLoading: boolean;
  onRefreshSnapshot: () => Promise<void>;
  onReloadTools: () => Promise<void>;
  onVerifyRuntime: () => Promise<void>;
  isReloading: boolean;
  isRuntimeBusy: boolean;
  isVerifying: boolean;
}

const VIEW_ITEMS: Array<{
  id: AppView;
  label: string;
  icon: LucideIcon;
}> = [
  { id: "chat", label: "Chat", icon: MessageSquare },
  { id: "command-center", label: "Command Center", icon: Command },
  { id: "posture", label: "Posture", icon: Shield },
  { id: "activity", label: "Activity", icon: Activity },
];

interface SnapshotItem {
  label: string;
  value: string;
  icon: LucideIcon;
}

function TopNavButton({
  active,
  label,
  icon: Icon,
  onClick,
}: {
  active: boolean;
  label: string;
  icon: LucideIcon;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        active
          ? "inline-flex h-header-height items-center gap-space-sm border-b-2 border-secondary text-sm font-semibold text-primary"
          : "inline-flex h-header-height items-center gap-space-sm text-sm font-medium text-text-muted transition hover:text-secondary"
      }
    >
      <Icon className="h-4 w-4" />
      {label}
    </button>
  );
}

function SnapshotRow({ item }: { item: SnapshotItem }) {
  const Icon = item.icon;

  return (
    <article className="rounded-lg px-space-sm py-space-sm transition-colors hover:bg-surface-container-high">
      <div className="flex items-center gap-space-sm">
        <Icon className="h-4 w-4 text-primary" />
        <div className="min-w-0 flex-1">
          <p className="font-medium text-primary">{item.label}</p>
          <p className="truncate text-xs text-text-muted">{item.value}</p>
        </div>
      </div>
    </article>
  );
}

export function AppShell({
  activeView,
  onViewChange,
  status,
  sessionId,
  isLoading,
  onRefreshSnapshot,
  onReloadTools,
  onVerifyRuntime,
  isReloading,
  isRuntimeBusy,
  isVerifying,
  children,
}: AppShellProps) {
  const snapshotItems: SnapshotItem[] = [
    {
      label: "Provider",
      value: status?.provider ?? (isLoading ? "Loading" : "Unavailable"),
      icon: Bot,
    },
    {
      label: "Inference",
      value: status?.inference_status ?? (isLoading ? "Loading" : "Unavailable"),
      icon: Activity,
    },
    {
      label: "Search",
      value: status?.search_status ?? (isLoading ? "Loading" : "Unavailable"),
      icon: Search,
    },
    {
      label: "Model",
      value: status?.model ?? (isLoading ? "Loading" : "Unavailable"),
      icon: Cpu,
    },
    {
      label: "Session",
      value: sessionId ? sessionId.slice(0, 12) : isLoading ? "Starting" : "Unavailable",
      icon: Fingerprint,
    },
  ];

  return (
    <div className="min-h-screen bg-background text-primary">
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-sidebar-width flex-col border-r border-border-subtle bg-surface-container px-space-sm py-space-md md:flex">
        <div className="border-b border-border-subtle px-space-sm pb-space-md">
          <div className="text-xl font-semibold text-primary">μZephyr</div>
          <div className="mt-1 flex items-center gap-space-sm text-sm text-text-muted">
            <span className={`h-2 w-2 rounded-full ${status?.runtime_initialized ? "bg-emerald-500" : "bg-amber-500"}`} />
            {status?.runtime_initialized ? "Live Environment" : "Initializing Runtime"}
          </div>
        </div>

        <div className="mt-space-md px-space-sm">
          <p className="text-base font-semibold text-primary">Runtime Snapshot</p>
          <p className="mt-1 text-xs text-text-muted">{status?.runtime_initialized ? "System Ready" : "Waiting for backend state"}</p>
        </div>

        <div className="mt-space-sm flex-1 space-y-1">
            {snapshotItems.map((item) => (
            <SnapshotRow key={item.label} item={item} />
          ))}
        </div>

        <button
          type="button"
          onClick={() => void onRefreshSnapshot()}
          className="mx-space-sm mt-space-md inline-flex items-center justify-center gap-space-sm rounded-lg bg-primary px-space-md py-space-sm text-sm font-semibold text-white transition hover:bg-primary/92"
        >
          <RefreshCw className="h-4 w-4" />
          Refresh Snapshot
        </button>

        <div className="mt-auto border-t border-border-subtle pt-space-md">
          <button type="button" className="flex w-full items-center gap-space-sm rounded-lg px-space-sm py-space-sm text-sm text-text-muted transition hover:bg-surface-container-high hover:text-primary">
            <BookOpen className="h-4 w-4" />
            Docs
          </button>
          <button type="button" className="mt-1 flex w-full items-center gap-space-sm rounded-lg px-space-sm py-space-sm text-sm text-text-muted transition hover:bg-surface-container-high hover:text-primary">
            <HelpCircle className="h-4 w-4" />
            Support
          </button>
        </div>
      </aside>

      <div className="flex min-h-screen flex-col md:ml-sidebar-width">
        <header className="sticky top-0 z-30 border-b border-border-subtle bg-surface/95 backdrop-blur">
          <div className="flex h-header-height items-center justify-between gap-space-md px-space-lg">
            <div className="flex items-center gap-space-xl">
              <div className="text-2xl font-semibold text-primary md:text-xl">μZephyr</div>
              <nav className="hidden items-center gap-space-lg md:flex">
                {VIEW_ITEMS.map((view) => (
                  <TopNavButton
                    key={view.id}
                    active={activeView === view.id}
                    label={view.label}
                    icon={view.icon}
                    onClick={() => onViewChange(view.id)}
                  />
                ))}
              </nav>
            </div>

            <div className="flex items-center gap-space-sm">
              <button
                type="button"
                onClick={() => void onReloadTools()}
                disabled={isRuntimeBusy}
                className="hidden items-center gap-space-sm rounded border border-primary px-space-md py-2 text-sm font-semibold text-primary transition hover:bg-surface-container-low disabled:cursor-not-allowed disabled:opacity-60 md:inline-flex"
              >
                <FolderSync className="h-4 w-4" />
                {isReloading ? "Reloading..." : "Reload tools"}
              </button>
              <button
                type="button"
                onClick={() => void onVerifyRuntime()}
                disabled={isVerifying}
                className="hidden items-center gap-space-sm rounded bg-accent px-space-md py-2 text-sm font-semibold text-white transition hover:bg-secondary disabled:cursor-not-allowed disabled:opacity-60 md:inline-flex"
              >
                <Shield className="h-4 w-4" />
                {isVerifying ? "Verifying..." : "Verify Runtime"}
              </button>
              <button type="button" className="inline-flex h-10 w-10 items-center justify-center rounded-lg text-text-muted transition hover:bg-surface-container-low hover:text-primary">
                <Settings className="h-5 w-5" />
              </button>
              <button type="button" className="inline-flex h-10 w-10 items-center justify-center rounded-lg text-text-muted transition hover:bg-surface-container-low hover:text-primary">
                <CircleUserRound className="h-5 w-5" />
              </button>
            </div>
          </div>

          <div className="overflow-x-auto border-t border-border-subtle px-space-md py-space-sm md:hidden">
            <div className="flex min-w-max items-center gap-space-lg">
              {VIEW_ITEMS.map((view) => (
                <TopNavButton
                  key={view.id}
                  active={activeView === view.id}
                  label={view.label}
                  icon={view.icon}
                  onClick={() => onViewChange(view.id)}
                />
              ))}
            </div>
          </div>
        </header>

        <main className="flex-1 px-space-lg py-space-lg pb-24">
          <div className="mx-auto max-w-[1200px]">{children}</div>
        </main>

        <footer className="fixed bottom-0 left-0 right-0 z-30 border-t border-border-subtle bg-surface px-space-lg py-2 md:left-sidebar-width">
          <div className="flex flex-col gap-space-sm text-xs text-text-muted sm:flex-row sm:items-center sm:justify-between">
            <div className="font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted">
              μZephyr v{status?.version ?? "0.1.0"} | {status?.runtime_initialized ? "SYSTEM_READY" : "INITIALIZING"}
            </div>
            <div className="flex items-center gap-space-md">
              <button type="button" className="transition hover:text-secondary">Terms</button>
              <button type="button" className="transition hover:text-secondary">Privacy</button>
              <button type="button" className="transition hover:text-secondary">API Docs</button>
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
}