import { TerminalSquare } from "lucide-react";

import type { RuntimeActionStreamEvent, RuntimePreparationResponse } from "../types/api";

interface RuntimeActivityPanelProps {
  activity: RuntimeActionStreamEvent | null;
  prepareResult: RuntimePreparationResponse | null;
  isReloading: boolean;
  isPreparing: boolean;
}

function badgeClasses(isActive: boolean, success: boolean | null): string {
  if (isActive) {
    return "border border-emerald-500/30 bg-emerald-50 text-emerald-700";
  }
  if (success === false) {
    return "border border-amber-500/30 bg-amber-50 text-amber-700";
  }
  if (success === true) {
    return "border border-emerald-500/30 bg-emerald-50 text-emerald-700";
  }
  return "border border-border-subtle bg-surface-container text-text-muted";
}

function logTone(line: string): string {
  const lowered = line.toLowerCase();
  if (lowered.includes("warn") || lowered.includes("warning")) {
    return "text-amber-400";
  }
  if (lowered.includes("error") || lowered.includes("failed")) {
    return "text-red-400";
  }
  return "text-emerald-400";
}

/**
 * Design reference: frontend/design.md -> Overview, Colors.
 */
export function RuntimeActivityPanel({
  activity,
  prepareResult,
  isReloading,
  isPreparing,
}: RuntimeActivityPanelProps) {
  const isActive = isReloading || isPreparing;
  const hasPrepareFallback = activity === null && prepareResult !== null;
  const actionLabel = activity
    ? activity.action === "reload"
      ? "Reload tools"
      : "Prepare runtime"
    : hasPrepareFallback
      ? "Prepare runtime"
      : "Runtime activity";
  const summary = activity
    ? activity.message
    : prepareResult
      ? `Last prepare run ${prepareResult.success ? "completed successfully" : "finished with warnings"}.`
      : "Reload and prepare now stream step-by-step progress instead of waiting for one final response.";
  const lines = activity?.lines ?? prepareResult?.lines ?? [];
  const badgeLabel = isActive ? "Live" : activity?.done ? (activity.success === false ? "Warnings" : "Complete") : prepareResult ? (prepareResult.success ? "Ready" : "Warnings") : "Idle";
  const success = activity?.success ?? (prepareResult ? prepareResult.success : null);

  return (
    <article className="flex flex-col overflow-hidden rounded-xl border border-border-subtle bg-surface shadow-sm">
      <div className="flex items-center justify-between border-b border-border-subtle bg-surface-container-lowest px-space-md py-space-sm">
        <h2 className="flex items-center gap-space-sm font-mono text-sm uppercase tracking-[0.18em] text-primary">
          <TerminalSquare className="h-4 w-4" />
          Runtime Activity
        </h2>
        <span className={`rounded px-2 py-1 font-mono text-[11px] uppercase tracking-[0.18em] ${badgeClasses(isActive, success)}`}>
          {badgeLabel}
        </span>
      </div>

      {lines.length > 0 ? (
        <div className="max-h-[400px] min-h-[320px] overflow-y-auto bg-[#1E1E1E] p-space-md font-mono text-sm text-slate-300">
          <div className="mb-space-md text-text-muted">{summary}</div>
          {lines.map((line, index) => (
            <div key={`${line}-${index}`} className="mb-2 flex gap-4">
              <span className="w-20 shrink-0 text-slate-500">step {String(index + 1).padStart(2, "0")}</span>
              <span className={logTone(line)}>{line}</span>
            </div>
          ))}
        </div>
      ) : (
        <div className="min-h-[320px] bg-[#1E1E1E] p-space-md font-mono text-sm text-slate-300">
          <div className="mb-2 text-slate-500">step 01</div>
          <div className="text-emerald-400">{summary}</div>
          <div className="mt-space-md text-slate-500">The live activity log will appear here when a runtime action starts.</div>
        </div>
      )}
    </article>
  );
}