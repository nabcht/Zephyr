import type { StartupGuidance } from "../types/api";

interface StartupGuidancePanelProps {
  guidance: StartupGuidance;
  prepareActions?: string[];
}

/**
 * Design reference: frontend/design.md -> Overview, Colors.
 */
export function StartupGuidancePanel({
  guidance,
  prepareActions = [],
}: StartupGuidancePanelProps) {
  if (guidance.actions.length === 0) {
    return (
      <section className="rounded-3xl border border-emerald-200 bg-emerald-50 p-5">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-[0.24em] text-emerald-700/70">Startup guidance</p>
            <h2 className="mt-2 text-xl font-semibold text-emerald-900">Runtime ready</h2>
          </div>
          <span className="rounded-full bg-emerald-600 px-3 py-1 text-xs font-semibold uppercase tracking-[0.24em] text-white">
            Ready
          </span>
        </div>

        {prepareActions.length > 0 ? (
          <div className="mt-5 rounded-2xl border border-emerald-200 bg-white/80 p-4 text-sm leading-6 text-emerald-900">
            Local prepare actions available for: {prepareActions.join(", ")}.
          </div>
        ) : null}
      </section>
    );
  }

  return (
    <section className="rounded-3xl border border-primary/10 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.24em] text-primary/55">Startup guidance</p>
          <h2 className="mt-2 text-xl font-semibold text-primary">{guidance.title}</h2>
        </div>
        <span className="rounded-full bg-accent px-3 py-1 text-xs font-semibold uppercase tracking-[0.24em] text-white">
          {guidance.badge}
        </span>
      </div>

      <div className="mt-5 space-y-4">
        {guidance.actions.map((action) => (
          <article key={`${action.label}-${action.summary}`} className="rounded-2xl border border-primary/10 bg-background p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="space-y-2">
                <h3 className="text-sm font-semibold uppercase tracking-[0.2em] text-primary">{action.label}</h3>
                <p className="text-sm leading-6 text-primary/75">{action.summary}</p>
              </div>
              <span className="inline-flex rounded-full bg-primary px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-background">
                {action.level}
              </span>
            </div>
            {action.command ? (
              <code className="mt-3 block overflow-x-auto rounded-xl bg-primary px-3 py-2 text-xs text-background/90">
                {action.command}
              </code>
            ) : null}
          </article>
        ))}

        {prepareActions.length > 0 ? (
          <article className="rounded-2xl border border-accent/20 bg-accent/10 p-4">
            <h3 className="text-sm font-semibold uppercase tracking-[0.2em] text-primary">Prepare in app</h3>
            <p className="mt-2 text-sm leading-6 text-primary/75">
              The current runtime can prepare local assets for: {prepareActions.join(", ")}.
            </p>
          </article>
        ) : null}
      </div>
    </section>
  );
}