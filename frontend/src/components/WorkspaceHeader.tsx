import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

interface WorkspaceHeaderProps {
  eyebrow: string;
  title: string;
  subtitle?: string;
  icon: LucideIcon;
  actions?: ReactNode;
}

export function WorkspaceHeader({
  eyebrow,
  title,
  subtitle,
  icon: Icon,
  actions,
}: WorkspaceHeaderProps) {
  return (
    <section className="rounded-xl border border-border-subtle bg-background px-space-md py-space-sm">
      <div className="flex flex-col gap-space-sm lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-start gap-space-sm">
          <Icon className="mt-1 h-6 w-6 text-primary" />
          <div>
            <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-text-muted">{eyebrow}</p>
            <h1 className="mt-1 text-xl font-semibold text-primary sm:text-2xl">{title}</h1>
            {subtitle ? <p className="mt-1 text-sm leading-6 text-text-muted">{subtitle}</p> : null}
          </div>
        </div>

        {actions ? <div className="flex items-center gap-space-sm">{actions}</div> : null}
      </div>
    </section>
  );
}