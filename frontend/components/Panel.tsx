import type { ReactNode } from "react";

/** A slightly-elevated surface panel with an optional title and header slot. */
export function Panel({
  title,
  actions,
  children,
  className = "",
  bodyClassName = "",
}: {
  title?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <section
      className={`flex min-h-0 flex-col overflow-hidden rounded-lg border border-border bg-surface ${className}`}
    >
      {(title || actions) && (
        <header className="flex shrink-0 items-center justify-between border-b border-border px-3 py-2">
          {title && (
            <h2 className="text-xs font-semibold uppercase tracking-wider text-text-muted">
              {title}
            </h2>
          )}
          {actions}
        </header>
      )}
      <div className={`min-h-0 flex-1 ${bodyClassName}`}>{children}</div>
    </section>
  );
}
