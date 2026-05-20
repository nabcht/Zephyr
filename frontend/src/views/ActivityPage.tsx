import { Activity, AlertTriangle, CheckSquare, Square } from "lucide-react";

import { ExecutionModeBanner } from "../components/ExecutionModeBanner";
import { RuntimeActivityPanel } from "../components/RuntimeActivityPanel";
import { WorkspaceHeader } from "../components/WorkspaceHeader";
import type {
  RuntimeActionStreamEvent,
  RuntimePreparationResponse,
  RuntimeVerification,
  StartupGuidance,
  SystemStatus,
} from "../types/api";

interface ActivityPageProps {
  status: SystemStatus | null;
  isStatusLoading: boolean;
  activity: RuntimeActionStreamEvent | null;
  prepareResult: RuntimePreparationResponse | null;
  verification: RuntimeVerification | null;
  isReloading: boolean;
  isPreparing: boolean;
  safetyConfirmationRequired: boolean | null;
  startupGuidance: StartupGuidance;
  onPrepareRuntime: () => Promise<void>;
}

function formatMetricMs(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "--";
  }

  return `${value.toFixed(1)} ms`;
}

function formatCount(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "--";
  }

  return String(value);
}

function readinessPanelClasses(value: string): string {
  const lowered = value.toLowerCase();
  if (lowered.includes("ready")) {
    return "border-emerald-500/30 bg-emerald-50";
  }
  if (lowered.includes("degraded") || lowered.includes("fallback") || lowered.includes("failed")) {
    return "border-amber-500/30 bg-amber-50";
  }
  return "border-border-subtle bg-surface-container-low";
}

function verificationLabel(verification: RuntimeVerification | null): string {
  if (!verification) {
    return "Not run yet";
  }
  if (verification.broken_skills.length > 0) {
    return "Needs attention";
  }
  return "Clean";
}

export function ActivityPage({
  status,
  isStatusLoading,
  activity,
  prepareResult,
  verification,
  isReloading,
  isPreparing,
  safetyConfirmationRequired,
  startupGuidance,
  onPrepareRuntime,
}: ActivityPageProps) {
  const warningAction = startupGuidance.actions[0] ?? null;

  return (
    <div className="space-y-6">
      <WorkspaceHeader
        eyebrow="Activity"
        title="System health and runtime activity"
        subtitle="Track live runtime actions, preparation output, validation state, and operational readiness from a single activity-focused page."
        icon={Activity}
      />

      <ExecutionModeBanner safetyConfirmationRequired={safetyConfirmationRequired} />

      {warningAction ? (
        <section className="rounded-lg border border-amber-500/30 bg-amber-50 p-space-md">
          <div className="flex items-start gap-space-md">
            <AlertTriangle className="mt-1 h-5 w-5 text-amber-500" />
            <div>
              <div className="font-semibold text-primary">{warningAction.label}</div>
              <div className="mt-1 text-sm leading-6 text-text-muted">{warningAction.summary}</div>
            </div>
          </div>
        </section>
      ) : null}

      <div className="grid gap-space-lg lg:grid-cols-3">
        <RuntimeActivityPanel
          activity={activity}
          prepareResult={prepareResult}
          isReloading={isReloading}
          isPreparing={isPreparing}
        />

        <div className="flex flex-col gap-space-lg">
          <section className="rounded-xl border border-border-subtle bg-surface p-space-md shadow-sm">
            <h2 className="mb-space-md flex items-center gap-space-xs border-b border-border-subtle pb-space-sm font-mono text-sm uppercase tracking-[0.18em] text-primary">
              <CheckSquare className="h-4 w-4" />
              Startup Guidance
            </h2>
            <div className="flex flex-col gap-space-sm">
              {startupGuidance.actions.length ? (
                startupGuidance.actions.map((action) => (
                  <label key={`${action.label}-${action.summary}`} className="flex items-start gap-space-sm rounded p-space-sm transition-colors hover:bg-surface-container-low">
                    <Square className="mt-0.5 h-4 w-4 text-primary" />
                    <div>
                      <div className="text-sm font-medium text-primary">{action.label}</div>
                      <div className="mt-1 text-xs leading-5 text-text-muted">{action.summary}</div>
                    </div>
                  </label>
                ))
              ) : (
                <label className="flex items-start gap-space-sm rounded p-space-sm">
                  <CheckSquare className="mt-0.5 h-4 w-4 text-emerald-600" />
                  <div>
                    <div className="text-sm font-medium text-primary line-through opacity-70">Runtime ready</div>
                    <div className="mt-1 text-xs leading-5 text-text-muted">No startup actions are currently required.</div>
                  </div>
                </label>
              )}
            </div>
          </section>

          <section className="rounded-xl border border-border-subtle bg-surface p-space-md shadow-sm">
            <div className="mb-space-md border-b border-border-subtle pb-space-sm font-mono text-sm uppercase tracking-[0.18em] text-primary">
              Runtime Readiness
            </div>
            <div className="grid gap-space-sm">
              <article className={`rounded-lg border p-space-sm ${readinessPanelClasses(status?.inference_status ?? "")}`}>
                <div className="font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted">Inference Runtime</div>
                <div className="mt-2 text-sm font-semibold text-primary">{status?.inference_status ?? (isStatusLoading ? "Loading" : "Unavailable")}</div>
                <div className="mt-1 text-xs leading-5 text-text-muted">Active provider readiness for the next live turn.</div>
              </article>

              <article className={`rounded-lg border p-space-sm ${readinessPanelClasses(status?.search_status ?? "")}`}>
                <div className="font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted">Search Runtime</div>
                <div className="mt-2 text-sm font-semibold text-primary">{status?.search_status ?? (isStatusLoading ? "Loading" : "Unavailable")}</div>
                <div className="mt-1 text-xs leading-5 text-text-muted">Semantic and keyword search readiness for search-backed tools.</div>
              </article>
            </div>
          </section>

          <section className="rounded-xl border border-border-subtle bg-surface p-space-md shadow-sm">
            <div className="mb-space-md border-b border-border-subtle pb-space-sm font-mono text-sm uppercase tracking-[0.18em] text-primary">
              Runtime Metrics
            </div>
            <div className="grid grid-cols-2 gap-space-md">
              <div>
                <div className="font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted">Loaded Tools</div>
                <div className="mt-1 text-2xl font-semibold text-primary">{status ? status.tool_counts.total : isStatusLoading ? "..." : "0"}</div>
              </div>
              <div>
                <div className="font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted">Skill Tools</div>
                <div className="mt-1 text-2xl font-semibold text-primary">{status ? status.tool_counts.skill_tools : isStatusLoading ? "..." : "0"}</div>
              </div>
              <div>
                <div className="font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted">Remote Caps</div>
                <div className="mt-1 text-2xl font-semibold text-primary">{status ? status.privacy_status.remote_capabilities.length : isStatusLoading ? "..." : "0"}</div>
              </div>
              <div>
                <div className="font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted">Interfaces</div>
                <div className="mt-1 text-2xl font-semibold text-primary">{status ? status.interfaces.length : isStatusLoading ? "..." : "0"}</div>
              </div>
              <div>
                <div className="font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted">Provider Warm-up</div>
                <div className="mt-1 text-2xl font-semibold text-primary">{formatMetricMs(status?.inference_metrics?.last_warmup_milliseconds)}</div>
                <div className="mt-1 text-xs leading-5 text-text-muted">{status?.inference_metrics?.last_warmup_outcome ?? "not_run"}</div>
              </div>
              <div>
                <div className="font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted">First Response Token</div>
                <div className="mt-1 text-2xl font-semibold text-primary">{formatMetricMs(status?.inference_metrics?.first_response_token_milliseconds)}</div>
                <div className="mt-1 text-xs leading-5 text-text-muted">{status?.inference_metrics?.first_response_token_outcome ?? "not_run"}</div>
              </div>
              <div>
                <div className="font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted">Last Provider Call</div>
                <div className="mt-1 text-2xl font-semibold text-primary">{formatMetricMs(status?.inference_metrics?.last_completion_milliseconds)}</div>
                <div className="mt-1 text-xs leading-5 text-text-muted">{status?.inference_metrics?.last_completion_outcome ?? "not_run"}</div>
              </div>
              <div>
                <div className="font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted">Payload Size</div>
                <div className="mt-1 text-2xl font-semibold text-primary">{formatCount(status?.provider_payload_metrics?.serialized_payload_characters)}</div>
                <div className="mt-1 text-xs leading-5 text-text-muted">Serialized provider payload characters.</div>
              </div>
              <div>
                <div className="font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted">History Messages</div>
                <div className="mt-1 text-2xl font-semibold text-primary">{formatCount(status?.provider_payload_metrics?.history_message_count)}</div>
                <div className="mt-1 text-xs leading-5 text-text-muted">Prior conversation messages included in the first provider request.</div>
              </div>
              <div>
                <div className="font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted">Provider Messages</div>
                <div className="mt-1 text-2xl font-semibold text-primary">{formatCount(status?.provider_payload_metrics?.provider_message_count)}</div>
                <div className="mt-1 text-xs leading-5 text-text-muted">Total messages sent in the first provider request.</div>
              </div>
              <div>
                <div className="font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted">Tool Schemas</div>
                <div className="mt-1 text-2xl font-semibold text-primary">{formatCount(status?.provider_payload_metrics?.tool_schema_count)}</div>
                <div className="mt-1 text-xs leading-5 text-text-muted">Function-calling tool schemas included with the first provider request.</div>
              </div>
              <div>
                <div className="font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted">Lightweight Payload</div>
                <div className="mt-1 text-2xl font-semibold text-primary">
                  {status?.provider_payload_metrics?.used_lightweight_payload_strategy == null
                    ? "--"
                    : status.provider_payload_metrics.used_lightweight_payload_strategy
                      ? "Yes"
                      : "No"}
                </div>
                <div className="mt-1 text-xs leading-5 text-text-muted">Whether the first provider request skipped tool schemas and prior history.</div>
              </div>
            </div>

            <button
              type="button"
              onClick={() => void onPrepareRuntime()}
              disabled={isPreparing || isReloading}
              className="mt-space-md inline-flex items-center justify-center rounded border border-primary px-space-md py-space-sm text-sm font-semibold text-primary transition hover:bg-surface-container-low disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isPreparing ? "Preparing..." : "Prepare Runtime"}
            </button>
          </section>

          <section className="rounded-xl border border-border-subtle bg-surface p-space-md shadow-sm">
            <div className="font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted">Verification Snapshot</div>
            <div className="mt-2 text-xl font-semibold text-primary">{verificationLabel(verification)}</div>
            <div className="mt-3 text-sm leading-6 text-text-muted">
              {verification
                ? `${verification.valid_skills.length} valid, ${verification.repaired_skills.length} repaired, ${verification.broken_skills.length} broken.`
                : "Run Verify Runtime from the top navigation to surface the browser-side verification result here."}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}