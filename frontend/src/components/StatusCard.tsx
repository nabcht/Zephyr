import type { ReactNode } from "react";

interface StatusCardProps {
  label: string;
  value: string;
  detail?: string;
  icon: ReactNode;
}

/**
 * Design reference: frontend/design.md -> Colors.
 */
export function StatusCard({ label, value, detail, icon }: StatusCardProps) {
  return (
    <article className="rounded-3xl border border-primary/10 bg-background/90 p-5 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-2">
          <p className="text-xs uppercase tracking-[0.24em] text-primary/55">{label}</p>
          <p className="text-2xl font-semibold tracking-tight text-primary">{value}</p>
          {detail ? <p className="text-sm leading-6 text-primary/70">{detail}</p> : null}
        </div>
        <div className="rounded-2xl bg-accent/10 p-3 text-accent">{icon}</div>
      </div>
    </article>
  );
}