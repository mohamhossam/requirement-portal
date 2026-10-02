import { ChevronDown, ChevronRight } from "lucide-react";
import { Link } from "react-router-dom";

import type { RequirementWorklistItem } from "../../api/client";
import { Badge } from "../../components/ui/Badge";
import { HOVER_GROUND_SOFT, TRANSITION } from "../../components/ui/recipes";
import { NextAction } from "../requirement/NextAction";
import { stagePath } from "../stagePath";
import { actorLabel, nextActionLabels, statusBadge, statusLabels, updatedLabel } from "./labels";

/**
 * Where the day starts (docs/ux-plan.md Phase 1: "the attention strip reworked
 * as the primary entry point").
 *
 * The highest-priority item is the screen's one Next block — the only element
 * in the product allowed to tell somebody what to do, and the one place this
 * screen spends the accent (§4.4, §11). The rest follow as a short list, each
 * with its status, what it is waiting on, and how long it has waited, so a BA
 * can see the shape of the morning before choosing where to start.
 *
 * It used to be a thin band of look-alike rows, and before that a three-column
 * grid of cards that left two thirds of the panel empty for the common case of
 * one item. Absent when nothing needs attention: an empty "all clear" box would
 * be one more thing to read on the screen opened most often.
 */
export function AttentionStrip({
  items,
  open,
  onToggle,
}: {
  items: RequirementWorklistItem[];
  open: boolean;
  onToggle: () => void;
}) {
  if (items.length === 0) return null;
  const [first, ...rest] = items;
  return (
    /* `minmax(0,1fr)`, not the implicit auto column: an auto track takes its
       minimum from its widest item, and a truncated one-line title still counts
       at full width there — `min-w-0` does not lower a contribution. A long
       title in the Next block stretched this whole section to 465px at 375. */
    <section aria-labelledby="attention-title" className="grid grid-cols-[minmax(0,1fr)] gap-3">
      {/* The disclosure pattern: the button inside the heading, not a heading
          inside a button, which is not valid content for one. */}
      <h2 id="attention-title" className="text-headline m-0">
        <button
          className="text-ink flex min-h-8 w-fit cursor-pointer flex-wrap items-center gap-x-2 rounded-sm border-0 bg-transparent px-1 text-left [font:inherit]"
          type="button"
          aria-expanded={open}
          aria-controls="attention-items"
          onClick={onToggle}
        >
          {open ? <ChevronDown size={16} aria-hidden="true" /> : <ChevronRight size={16} aria-hidden="true" />}
          Needs attention
          <span className="text-meta text-ink-muted font-normal tabular-nums">
            {items.length === 1 ? "1 requirement is waiting on a person" : `${items.length} requirements are waiting on a person`}
          </span>
        </button>
      </h2>
      {open && first && (
        <div id="attention-items" className="grid grid-cols-[minmax(0,1fr)] gap-3">
          <NextAction
            action={{ label: nextActionLabels[first.next_action], to: stagePath(first) }}
            detail={first.title}
            here=""
          />
          {rest.length > 0 && (
            <ul
              aria-label="Also waiting"
              className="border-line bg-surface m-0 list-none overflow-hidden rounded-md border border-solid p-0"
            >
              {rest.map((item) => {
                const badge = statusBadge[item.workflow_status];
                const Icon = badge.icon;
                return (
                  <li key={item.id} className="[&+li]:[border-top:1px_solid_var(--line)]">
                    <Link
                      className={`text-ink flex min-h-11 items-center gap-3 px-4 py-2 no-underline ${HOVER_GROUND_SOFT} ${TRANSITION}`}
                      to={stagePath(item)}
                    >
                      {/* Two lines below `md` — what it is, then what it needs —
                          because one line at 375px left the title one letter. */}
                      <span className="grid min-w-0 flex-1 grid-cols-[minmax(0,1fr)] gap-1 md:flex md:items-center md:gap-3">
                        <span className="flex min-w-0 items-center gap-2 md:flex-1">
                          <Badge tone={badge.tone} icon={<Icon aria-hidden={true} className="shrink-0" size={12} />}>
                            {statusLabels[item.workflow_status]}
                          </Badge>
                          <strong className="text-body min-w-0 truncate font-semibold">{item.title}</strong>
                        </span>
                        <span className="text-body text-ink-soft">{nextActionLabels[item.next_action]}</span>
                        <span className="text-meta text-ink-muted tabular-nums max-lg:hidden">
                          {updatedLabel(item.last_activity?.occurred_at ?? item.updated_at)} · {actorLabel(item)}
                        </span>
                      </span>
                      <ChevronRight className="text-ink-muted shrink-0" size={16} aria-hidden="true" />
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}
