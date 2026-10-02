import { ArrowRight } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { cx } from "../../components/ui/cx";
import { TRANSITION } from "../../components/ui/recipes";

/**
 * What this Requirement is waiting on — one per workspace, and the only element
 * in the product allowed to tell somebody what to do (docs/design-system.md §11).
 *
 * A bordered block with a 3px `--accent` left edge, a small uppercase `NEXT`
 * marker and the action in the person's own words. `NEXT` is the single place
 * uppercase survives in the type system (§5): there it is a symbol rather than a
 * word.
 *
 * When the work is here it reads as a statement; when it is elsewhere it takes
 * you there.
 */
const SHELL =
  "border-line bg-surface text-body m-0 flex items-center gap-2 rounded-sm border" +
  " border-solid border-l-[3px] border-l-[var(--accent)] px-3 py-2";

const MARKER = "text-accent text-label uppercase [letter-spacing:0.08em]";

export function NextAction({
  action,
  here,
  detail,
}: {
  action: { label: string; to: string };
  here: string;
  /**
   * What the action is on, when the screen is not already that thing — the
   * worklist names the requirement after its next step. Muted, so the action
   * still reads first.
   */
  detail?: ReactNode;
}) {
  const detailText = detail ? <span className="text-ink-muted min-w-0 truncate">{detail}</span> : null;
  if (action.to === here) {
    return (
      <p className={SHELL}>
        <span className={MARKER}>Next</span>
        <span className="text-ink">{action.label}</span>
        {detailText}
      </p>
    );
  }
  return (
    <Link
      className={cx(SHELL, TRANSITION, "no-underline hover:border-accent hover:bg-accent-wash")}
      to={action.to}
    >
      <span className={MARKER}>Next</span>
      <span className="text-ink">{action.label}</span>
      {detailText}
      <ArrowRight className="text-accent ml-auto" size={15} aria-hidden="true" />
    </Link>
  );
}
