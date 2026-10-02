import { ChevronRight } from "lucide-react";
import type { ReactNode } from "react";

import { cx } from "./ui/cx";

/**
 * A labelled `<details>` that still looks like one.
 *
 * The backlog's disclosures had lost their affordance: `summary { display: flex }`
 * drops the native marker in every engine, so "System impact", "Splitting
 * rationale" and "Successful checks" rendered as plain bold headings with no
 * sign they opened anything. The marker is a drawn chevron now, hidden from
 * assistive technology because `<summary>` already announces its own expanded
 * state.
 *
 * Still a `<details>`, and still pushes rather than floats: Escape, Find-in-page
 * and the keyboard all work without a line of script.
 */
export function Disclosure({
  label,
  children,
  className,
  defaultOpen = false,
  id,
}: {
  label: ReactNode;
  children: ReactNode;
  className?: string;
  /** Open on first render. Still the person's to close; not controlled after. */
  defaultOpen?: boolean;
  id?: string;
}) {
  return (
    <details className={cx("workspace-disclosure group", className)} id={id} open={defaultOpen || undefined}>
      <summary>
        <ChevronRight
          aria-hidden="true"
          size={15}
          className="text-ink-muted shrink-0 transition-transform duration-[var(--motion-fast)] ease-out group-open:rotate-90 motion-reduce:transition-none"
        />
        {label}
      </summary>
      <div className="pt-2">{children}</div>
    </details>
  );
}
