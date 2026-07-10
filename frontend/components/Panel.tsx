import type { ReactNode } from "react";

/** Card panel: rounded-xl, shadowed, no hard borders — modern SaaS aesthetic. */
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
      className={`flex min-h-0 flex-col overflow-hidden rounded-xl bg-surface shadow-sm ${className}`}
    >
      {(title || actions) && (
        <header className="flex shrink-0 items-center justify-between px-4 py-3">
          {title && (
            <h2 className="text-xs font-semibold text-text-muted">
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
