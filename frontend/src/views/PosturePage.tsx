import { Database, Shield } from "lucide-react";

import { RuntimeSignalsPanel } from "../components/RuntimeSignalsPanel";
import { WorkspaceHeader } from "../components/WorkspaceHeader";
import type { PrivacyStatus, RuntimeTrustStatus } from "../types/api";

interface PosturePageProps {
  privacyStatus: PrivacyStatus;
  trustStatus: RuntimeTrustStatus;
  memoryFacts: string[];
}

export function PosturePage({
  privacyStatus,
  trustStatus,
  memoryFacts,
}: PosturePageProps) {
  return (
    <div className="space-y-6">
      <WorkspaceHeader
        eyebrow="Posture"
        title="Trust & Privacy Posture"
        subtitle="Continuous visibility into the runtime trust layer, inference privacy boundaries, and durable memory transparency."
        icon={Shield}
      />

      <RuntimeSignalsPanel
        privacyStatus={privacyStatus}
        trustStatus={trustStatus}
        durableFactCount={memoryFacts.length}
      />

      <section className="rounded-xl border border-border-subtle bg-surface-container-lowest p-space-lg">
        <div className="mb-space-md flex items-center gap-space-sm border-b border-border-subtle pb-space-sm">
          <Database className="h-5 w-5 text-primary" />
          <h2 className="text-xl font-semibold text-primary">Durable Memory Facts</h2>
          <span className="ml-auto rounded bg-surface-container px-2 py-1 font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted">
            Transparency Report
          </span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-border-subtle font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted">
                <th className="px-4 py-2 font-medium">Fact Entity</th>
                <th className="px-4 py-2 font-medium">Source</th>
                <th className="px-4 py-2 font-medium">Retention Policy</th>
                <th className="px-4 py-2 font-medium">Action</th>
              </tr>
            </thead>
            <tbody>
              {memoryFacts.length ? (
                memoryFacts.map((fact, index) => (
                  <tr key={fact} className="border-b border-border-subtle transition-colors hover:bg-surface-container-low last:border-b-0">
                    <td className="px-4 py-3 font-medium text-primary">Fact {index + 1}</td>
                    <td className="px-4 py-3 text-text-muted">Durable Memory</td>
                    <td className="px-4 py-3 text-primary">Persistent</td>
                    <td className="px-4 py-3 text-text-muted">{fact}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={4} className="px-4 py-6 text-center text-text-muted">
                    No durable facts are stored yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}