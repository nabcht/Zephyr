import type { PropsWithChildren, ReactNode } from "react";

interface DesignWrapperProps extends PropsWithChildren {
  eyebrow: string;
  title: string;
  subtitle: string;
  actions?: ReactNode;
}

/**
 * Design reference: frontend/design.md -> Overview, Colors.
 */
export function DesignWrapper({
  eyebrow,
  title,
  subtitle,
  actions,
  children,
}: DesignWrapperProps) {
  return (
    <div className="min-h-screen bg-background text-primary">
      <div className="mx-auto flex min-h-screen max-w-6xl flex-col px-4 py-8 sm:px-6 lg:px-8">
        <header className="overflow-hidden rounded-[28px] border border-primary/10 bg-primary px-6 py-8 text-background shadow-terminal sm:px-10">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl space-y-4">
              <p className="text-xs uppercase tracking-[0.35em] text-background/70">{eyebrow}</p>
              <div className="space-y-3">
                <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">{title}</h1>
                <p className="max-w-2xl text-sm leading-6 text-background/78 sm:text-base">{subtitle}</p>
              </div>
            </div>
            {actions ? <div className="flex items-center gap-3">{actions}</div> : null}
          </div>
        </header>

        <main className="relative mt-6 flex-1 overflow-hidden rounded-[28px] border border-primary/10 bg-white/90 shadow-terminal backdrop-blur">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(184,66,46,0.08),transparent_38%),linear-gradient(rgba(26,28,30,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(26,28,30,0.03)_1px,transparent_1px)] bg-[length:auto,22px_22px,22px_22px]" />
          <div className="relative h-full p-6 sm:p-8">{children}</div>
        </main>
      </div>
    </div>
  );
}