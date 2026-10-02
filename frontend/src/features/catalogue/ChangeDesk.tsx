import { ChevronDown, TriangleAlert } from "lucide-react";
import { useId, useState, type ReactNode } from "react";

import type { KnowledgeRelease } from "../../api/knowledge";
import { Badge, cx } from "../../components/ui";
import { FOCUS_RING, TRANSITION } from "../../components/ui/recipes";
import { formatTime, versionName } from "./labels";

/**
 * The Change desk: a rail beside the workbench that always says which version
 * requirement mapping reads, whether one is in progress, and what is next. It
 * is sticky on wide screens. Below `lg` it folds to a one-line summary above
 * the workbench, so the systems stay in the first viewport; the summary opens
 * the whole desk in place.
 */
export function ChangeDesk({ summary, collapseKey, children }: {
  summary: ReactNode;
  /** When this changes (a step opens or closes), the folded desk folds again so the work is in view. */
  collapseKey?: unknown;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const [seenKey, setSeenKey] = useState(collapseKey);
  if (seenKey !== collapseKey) {
    setSeenKey(collapseKey);
    setOpen(false);
  }
  const bodyId = useId();
  return (
    <aside aria-label="Change desk"
      className={cx(
        "bg-surface-sunken border-line grid min-w-0 content-start rounded-md border border-solid",
        "lg:sticky lg:top-[calc(var(--header-height)+var(--space-6))] lg:max-h-[calc(100dvh-var(--header-height)-var(--space-12))] lg:overflow-y-auto lg:overscroll-contain",
      )}>
      <button type="button" aria-expanded={open} aria-controls={bodyId} onClick={() => setOpen((value) => !value)}
        className={cx("text-body text-ink flex min-h-11 w-full cursor-pointer items-center gap-2 rounded-md border-0 bg-transparent px-4 py-2 text-left lg:hidden",
          FOCUS_RING, TRANSITION)}>
        <span className="min-w-0 flex-1">{summary}</span>
        <ChevronDown size={16} aria-hidden="true"
          className={cx("text-ink-muted shrink-0 motion-safe:transition-transform", open && "rotate-180")} />
      </button>
      <div id={bodyId}
        className={cx(
          "min-w-0 content-start gap-4 p-4 lg:grid",
          "[&>*+*]:border-line [&>*+*]:border-0 [&>*+*]:border-t [&>*+*]:border-solid [&>*+*]:pt-4",
          open ? "border-line grid border-0 border-t border-solid lg:border-t-0" : "hidden",
        )}>
        {children}
      </div>
    </aside>
  );
}

/** The version in use: what mapping reads today, and how much of the backlog still reads an older one. */
export function LiveVersion({ current, outdated }: { current: KnowledgeRelease | undefined; outdated?: number }) {
  return (
    <section aria-labelledby="in-use-title" className="grid gap-1.5">
      <div className="flex min-w-0 flex-wrap items-center gap-2">
        <h2 className="text-title text-ink m-0 break-words" id="in-use-title">
          {current ? versionName(current) : "Loading the version in use…"}
        </h2>
        {current && <Badge tone="success">In use</Badge>}
      </div>
      {current && (
        <>
          <p className="text-meta text-ink-soft m-0 tabular-nums">
            {current.systems.length} systems · {current.relationships.length} dependencies
          </p>
          <p className="text-meta text-ink-muted m-0">
            Requirement mapping reads this version
            {current.published_at && ` · published ${formatTime(current.published_at)} by ${current.published_by}`}
          </p>
        </>
      )}
      {(outdated ?? 0) > 0 && (
        <p className="bg-warning-wash text-ink-soft text-meta m-0 mt-1.5 flex gap-2 rounded-sm border-0 border-l-[3px] border-solid border-l-[var(--warning-edge)] px-3 py-2">
          <TriangleAlert className="text-warning mt-0.5 shrink-0" size={14} aria-hidden="true" />
          <span>
            {outdated === 1
              ? "1 requirement is still mapped with an older version."
              : `${outdated} requirements are still mapped with an older version.`}
            {" "}Their teams remap them from the requirement.
          </span>
        </p>
      )}
    </section>
  );
}
