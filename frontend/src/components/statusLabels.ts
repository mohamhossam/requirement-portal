import type { GenerationStatus } from "../api/client";

/**
 * The one map from a generation status to the words a person reads.
 *
 * `.replaceAll("_", " ")` stood in for this at six call sites and shipped
 * `needs_revision` to a business owner as "needs revision", which
 * docs/ux-plan.md §3.7 records as a direct breach of PRODUCT.md Principle 3 —
 * "a business owner should never need the method". §4 sets the rule this file
 * exists to keep: "One label map, in the presentation layer, for every enum the
 * API returns."
 *
 * Separate from StatusBadge so the badge file exports only its component.
 */
export const STATUS_LABEL: Record<GenerationStatus, string> = {
  generated: "Generated",
  edited: "Edited",
  approved: "Approved",
  needs_revision: "Needs revision",
};

export function statusLabel(status: GenerationStatus): string {
  return STATUS_LABEL[status] ?? status;
}

/**
 * What a backlog row says about itself. Staleness outranks status: a stale
 * approved item is not approved any more.
 *
 * "Out of date", the one name for it. The Backlog used three — "Needs
 * reconciliation" here, "Out of date" on the notice, "stale content" on the
 * banner — for one fact.
 */
export function backlogItemLabel(item: { status: string; stale?: unknown }): string {
  return item.stale ? "Out of date" : statusLabel(item.status as GenerationStatus);
}
