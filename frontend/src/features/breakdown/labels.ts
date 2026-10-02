import type { Approval, GenerationStatus } from "../../api/client";
import type { BadgeTone } from "../../components/ui";

/**
 * What a backlog item needs from a person, in their words.
 *
 * The Backlog used to print provenance alone — "Generated", "Edited",
 * "Approved" — so a Feature edited after its approval read as a quiet grey
 * "Edited" on the Epic page, when what it meant was "your sign-off lapsed; this
 * needs approving again". The baseline critique for Phase 4 put it plainly: the
 * Product Owner could not answer "what needs me?" without opening every item.
 *
 * A verdict is computed from what the item already carries — its status, its
 * staleness and its approval history — so no new request is made. Provenance
 * still has its own badge (`StatusBadge`); this is the other question.
 */
type BacklogItem = {
  status: GenerationStatus;
  stale?: unknown;
  current_approval?: Approval | null;
  approval_history?: Approval[];
};

export type Verdict = { label: string; tone: BadgeTone };

/**
 * Epics and Features are approved here; Stories are approved on Review &
 * approve, so a Story that is not approved is not "owed" on this screen and is
 * neutral rather than amber.
 */
export function backlogVerdict(item: BacklogItem, level: "epic" | "feature" | "story"): Verdict {
  if (item.stale) return { label: "Out of date", tone: "warning" };
  if (item.status === "approved") return { label: "Approved", tone: "success" };
  if (level === "story") return { label: "Not yet approved", tone: "neutral" };
  const lapsed = (item.approval_history ?? []).some((approval) => approval.decision === "approved");
  return { label: lapsed ? "Needs approving again" : "Needs approval", tone: "warning" };
}

/** An item that is owed a decision on this screen. */
export function needsApproval(item: BacklogItem): boolean {
  return Boolean(item.stale) || item.status !== "approved";
}

const TIMESTAMP = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });

/** One timestamp format for the Backlog, the same one ProvenanceDetails uses. */
export function when(iso: string): string {
  return TIMESTAMP.format(new Date(iso));
}

/**
 * Who signed, and when — the one fact that makes an approval a human act
 * rather than a green badge. Every Epic, Feature and Story response carries it;
 * the Backlog never showed it.
 */
export function signature(item: BacklogItem): string | null {
  const approval = item.current_approval;
  if (!approval || item.status !== "approved" || item.stale) return null;
  return `Approved by ${approval.recorded_by.display_name} · ${when(approval.recorded_at)}`;
}

export const DROP_LABEL = { mvp: "First release", later: "Later release" } as const;
