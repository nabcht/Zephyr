import { AlertTriangle, CheckCircle2, Database, ShieldCheck } from "lucide-react";

import type { PrivacyStatus, RuntimeTrustStatus } from "../types/api";

interface RuntimeSignalsPanelProps {
  privacyStatus: PrivacyStatus;
  trustStatus: RuntimeTrustStatus;
  durableFactCount: number;
}

/**
 * Design reference: frontend/design.md -> Overview, Colors.
 */
export function RuntimeSignalsPanel({
  privacyStatus,
  trustStatus,
  durableFactCount,
}: RuntimeSignalsPanelProps) {
  return (
    <section className="grid gap-space-md lg:grid-cols-3">
      <article className="relative overflow-hidden rounded-xl border border-primary bg-primary p-space-lg text-white shadow-sm lg:col-span-2">
        <ShieldCheck className="pointer-events-none absolute right-4 top-4 h-24 w-24 text-white/10" />
        <div className="relative z-10 flex items-start justify-between gap-space-md">
          <div>
            <h2 className="text-xl font-semibold">Runtime Trust Signals</h2>
            <p className="mt-1 text-sm text-white/70">Continuous validation of the execution environment.</p>
          </div>
          <span className="rounded border border-emerald-700 bg-emerald-900/60 px-2 py-1 font-mono text-[11px] uppercase tracking-[0.18em] text-emerald-300">
            {trustStatus.level === "green" ? "Secure Enclave" : trustStatus.badge}
          </span>
        </div>

        <div className="relative z-10 mt-space-md grid gap-space-md sm:grid-cols-2">
          {trustStatus.signals.map((signal) => {
            const isWarning = signal.level.toLowerCase() !== "green";
            return (
              <article key={signal.label} className="rounded-lg border border-white/15 bg-black/20 p-space-md">
                <div className="flex items-center justify-between gap-space-sm">
                  <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-white/65">{signal.label}</span>
                  {isWarning ? <AlertTriangle className="h-4 w-4 text-amber-300" /> : <CheckCircle2 className="h-4 w-4 text-emerald-300" />}
                </div>
                <div className="mt-2 text-sm font-semibold text-white">{signal.badge}</div>
                <div className="mt-2 text-sm leading-6 text-white/75">{signal.summary}</div>
              </article>
            );
          })}
        </div>
      </article>

      <article className="rounded-xl border border-border-subtle bg-surface-container-lowest p-space-lg">
        <div className="flex items-center gap-space-sm">
          <ShieldCheck className="h-5 w-5 text-primary" />
          <h2 className="text-xl font-semibold text-primary">Privacy Posture</h2>
        </div>

        <div className="mt-space-md space-y-4">
          <div className="border-b border-border-subtle pb-3">
            <div className="font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted">Inference Backend</div>
            <div className="mt-2 flex items-center justify-between gap-space-sm">
              <span className="text-sm text-primary">{privacyStatus.inference_backend}</span>
              <span className="rounded bg-surface-container-high px-2 py-1 font-mono text-[11px] uppercase tracking-[0.18em] text-primary">Active</span>
            </div>
          </div>

          <div className="border-b border-border-subtle pb-3">
            <div className="font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted">Remote Capabilities</div>
            <div className="mt-2 flex items-center justify-between gap-space-sm">
              <span className="text-sm text-primary">
                {privacyStatus.remote_capabilities.length > 0 ? privacyStatus.remote_capabilities.join(", ") : "Cloud Fallback"}
              </span>
              <span className="rounded bg-surface-container px-2 py-1 font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted">
                {privacyStatus.remote_capabilities.length > 0 ? `${privacyStatus.remote_capabilities.length} Enabled` : "Disabled"}
              </span>
            </div>
          </div>

          <div>
            <div className="flex items-center gap-space-sm font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted">
              <Database className="h-4 w-4" />
              Durable Memory Facts
            </div>
            <div className="mt-2 flex items-center justify-between gap-space-sm">
              <span className="text-sm text-primary">Persistent user and runtime facts</span>
              <span className="rounded bg-surface-container-high px-2 py-1 font-mono text-[11px] uppercase tracking-[0.18em] text-primary">
                {durableFactCount} Stored
              </span>
            </div>
            <p className="mt-3 text-sm leading-6 text-text-muted">{privacyStatus.summary}</p>
          </div>
        </div>
      </article>
    </section>
  );
}