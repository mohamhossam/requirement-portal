import type { BadgeTone } from "../../components/ui/Badge";
import type { RevisionHistory } from "../../api/client";
import { BREAKDOWN_STATUS_LABEL, BREAKDOWN_STATUS_TONE } from "../review/labels";

export type BacklogRevision = RevisionHistory["breakdown_revisions"][number];

/**
 * Where the backlog stood when this revision was recorded, in one phrase.
 *
 * A revision is a snapshot, not an event, so the phrase names the furthest
 * point the snapshot had reached: the review's own state once there is one,
 * otherwise the deepest level that exists. Read from fields the history
 * already returns; nothing is inferred beyond them.
 */
export function revisionState(revision: BacklogRevision): { label: string; tone: BadgeTone } {
  if (revision.exportable) return { label: "Approved for export", tone: "success" };
  const review = revision.review_status as keyof typeof BREAKDOWN_STATUS_LABEL | null;
  if (review && review in BREAKDOWN_STATUS_LABEL && review !== "generated") {
    return { label: BREAKDOWN_STATUS_LABEL[review], tone: BREAKDOWN_STATUS_TONE[review] };
  }
  if (revision.story_count > 0) return { label: "Stories drafted", tone: "neutral" };
  if (revision.feature_count > 0) return { label: "Features drafted", tone: "neutral" };
  if (revision.epic_status === "approved") return { label: "Epic approved", tone: "neutral" };
  if (revision.epic_name) return { label: "Epic drafted", tone: "neutral" };
  if (revision.analysis_human_confirmed) return { label: "Analysis confirmed", tone: "neutral" };
  if (revision.has_analysis) return { label: "Analysis drafted", tone: "neutral" };
  return { label: "No analysis yet", tone: "neutral" };
}

const plural = (count: number, one: string, many = `${one}s`) => `${count} ${count === 1 ? one : many}`;

/** "2 features (1 approved) · 4 stories" — what the backlog held. */
export function backlogContents(revision: BacklogRevision) {
  if (revision.feature_count === 0 && revision.story_count === 0) {
    return revision.epic_name ? "Epic only" : "No backlog yet";
  }
  const features =
    revision.approved_feature_count > 0 && revision.approved_feature_count < revision.feature_count
      ? `${plural(revision.feature_count, "feature")} (${revision.approved_feature_count} approved)`
      : plural(revision.feature_count, "feature");
  return `${features} and ${plural(revision.story_count, "story", "stories")}`;
}

/**
 * What a version changed against the one before it, in a few words: the
 * status move if there was one, then the first counts that moved. Read from
 * the two summaries; a version that moved nothing countable says so.
 */
export function changeSummary(previous: BacklogRevision | undefined, revision: BacklogRevision) {
  if (!previous) return "First version";
  const changes = factChanges(previous, revision);
  if (changes.length === 0) return "No change in status or counts";
  const status = changes.find((change) => change.label === "Status");
  const counts = changes.filter((change) => change.label !== "Status" && change.label !== "Epic");
  const parts = [
    status ? `${status.before} → ${status.after}` : null,
    ...counts.slice(0, status ? 1 : 2).map((change) => `${change.label}: ${change.before} → ${change.after}`),
  ].filter(Boolean);
  const more = counts.length - (status ? 1 : 2);
  return parts.join("; ") + (more > 0 ? `; ${more} more` : "");
}

export type NeedVersion = RevisionHistory["requirement_revisions"][number];

/** The business need version an approval was signed against: the last one saved before it. */
export function approvalBasis(needs: NeedVersion[], approvedAt: string | null) {
  if (!approvedAt) return null;
  return [...needs].reverse().find((need) => need.created_at <= approvedAt) ?? null;
}

export type DiffPart = { kind: "same" | "added" | "removed"; text: string };

/**
 * A word-level difference between two texts (longest common subsequence), so a
 * person can see what an edit to the business need actually changed instead of
 * reading both versions side by side.
 */
export function wordDiff(before: string, after: string): DiffPart[] {
  const a = before.split(/(\s+)/);
  const b = after.split(/(\s+)/);
  // Past a few thousand tokens the table gets large; fall back to whole-text.
  if (a.length * b.length > 4_000_000) {
    return before === after ? [{ kind: "same", text: after }] : [{ kind: "removed", text: before }, { kind: "added", text: after }];
  }
  const rows = a.length + 1;
  const cols = b.length + 1;
  const table = new Uint32Array(rows * cols);
  for (let i = a.length - 1; i >= 0; i -= 1) {
    for (let j = b.length - 1; j >= 0; j -= 1) {
      table[i * cols + j] = a[i] === b[j] ? table[(i + 1) * cols + j + 1]! + 1 : Math.max(table[(i + 1) * cols + j]!, table[i * cols + j + 1]!);
    }
  }
  const parts: DiffPart[] = [];
  const push = (kind: DiffPart["kind"], text: string) => {
    const last = parts.at(-1);
    if (last && last.kind === kind) last.text += text;
    else parts.push({ kind, text });
  };
  let i = 0;
  let j = 0;
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) {
      push("same", a[i]!);
      i += 1;
      j += 1;
    } else if (table[(i + 1) * cols + j]! >= table[i * cols + j + 1]!) {
      push("removed", a[i]!);
      i += 1;
    } else {
      push("added", b[j]!);
      j += 1;
    }
  }
  while (i < a.length) push("removed", a[i++]!);
  while (j < b.length) push("added", b[j++]!);
  return parts;
}

/** The facts worth comparing between two revisions, in the order a PO reads them. */
const FACTS: Array<{ label: string; read: (revision: BacklogRevision) => string | number }> = [
  { label: "Status", read: (revision) => revisionState(revision).label },
  { label: "Epic", read: (revision) => revision.epic_name ?? "None" },
  { label: "Features", read: (revision) => revision.feature_count },
  { label: "Features approved", read: (revision) => revision.approved_feature_count },
  { label: "Stories", read: (revision) => revision.story_count },
  { label: "Stories edited by a person", read: (revision) => revision.edited_story_count },
  { label: "Stories out of date", read: (revision) => revision.stale_story_count },
  { label: "Answered questions", read: (revision) => revision.clarification_count },
  { label: "Unresolved questions", read: (revision) => revision.unresolved_count },
  { label: "Analysis confirmed", read: (revision) => (revision.analysis_human_confirmed ? "Yes" : "No") },
  { label: "Approvals recorded", read: (revision) => revision.approval_count },
  { label: "Review blockers", read: (revision) => revision.review_blocker_count },
  { label: "Review comments", read: (revision) => revision.comment_count },
];

/** Only the facts that differ, so an unchanged count never reads as news. */
export function factChanges(from: BacklogRevision, to: BacklogRevision) {
  return FACTS.flatMap((fact) => {
    const before = fact.read(from);
    const after = fact.read(to);
    return before === after ? [] : [{ label: fact.label, before: String(before), after: String(after) }];
  });
}

/**
 * The comparison's own sentences, with the ID lists folded into a count. The
 * API names added, removed and changed Features and Stories only by ID; the count is
 * what a person reads, and the IDs stay one click away for anyone tracing them.
 */
export function readChange(change: string): { text: string; ids: string[] } {
  const match = /^(Features|Stories) (added|removed|changed): (.+)\.$/.exec(change);
  if (!match) return { text: change, ids: [] };
  const [, level, verb, list] = match;
  const ids = (list ?? "").split(",").map((id) => id.trim()).filter(Boolean);
  const noun = level === "Features" ? (ids.length === 1 ? "feature" : "features") : ids.length === 1 ? "story" : "stories";
  return { text: `${ids.length} ${noun} ${verb}.`, ids };
}

/** "26 Sep 2026, 18:19" — minutes, not seconds; the year only when it is not this one. */
export function whenLabel(iso: string) {
  const date = new Date(iso);
  return date.toLocaleString(undefined, {
    day: "numeric",
    month: "short",
    year: date.getFullYear() === new Date().getFullYear() ? undefined : "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
