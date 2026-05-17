import { CheckCircle2, Settings2, ShieldAlert } from "lucide-react";

interface ExecutionModeBannerProps {
  safetyConfirmationRequired: boolean | null;
}

/**
 * Design reference: frontend/design.md -> Overview, Colors.
 */
export function ExecutionModeBanner({
  safetyConfirmationRequired,
}: ExecutionModeBannerProps) {
  const isLoading = safetyConfirmationRequired === null;
  const automaticExecutionEnabled = safetyConfirmationRequired === false;

  const title = isLoading
    ? "Loading web execution mode"
    : automaticExecutionEnabled
      ? "Auto-Pilot Enabled"
      : "Manual Override Active";

  const summary = isLoading
    ? "Waiting for backend runtime status before rendering the current execution mode."
    : automaticExecutionEnabled
      ? "Sensitive tools execute immediately in the hybrid web interface when the runtime requests them."
      : "Sensitive tools require browser confirmation for each chat or mission turn.";

  const badge = isLoading
    ? "Loading"
    : automaticExecutionEnabled
      ? "Auto Execution"
      : "Confirmation Required";

  const Icon = isLoading ? Settings2 : automaticExecutionEnabled ? CheckCircle2 : ShieldAlert;
  const badgeClassName = isLoading
    ? "bg-primary text-white"
    : automaticExecutionEnabled
      ? "bg-emerald-600 text-white"
      : "bg-accent text-white";

  return (
    <section className="rounded-lg border border-border-subtle bg-surface p-space-md">
      <div className="flex flex-col gap-space-md sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-space-md">
          <div className={`flex h-10 w-10 items-center justify-center rounded-full ${automaticExecutionEnabled ? "bg-emerald-50 text-emerald-600" : "bg-primary text-white"}`}>
            <Icon className="h-5 w-5" />
          </div>
          <div>
            <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted">Execution Mode</p>
            <h2 className="text-xl font-semibold text-primary">{title}</h2>
            <p className="mt-1 text-sm leading-6 text-text-muted">{summary}</p>
          </div>
        </div>

        <span className={`inline-flex items-center justify-center rounded px-space-md py-space-sm text-sm font-semibold ${badgeClassName}`}>
          {badge}
        </span>
      </div>
    </section>
  );
}