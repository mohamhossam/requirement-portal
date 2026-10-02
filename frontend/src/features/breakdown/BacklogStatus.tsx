import { Check, TriangleAlert } from "lucide-react";

import type { Approval, GenerationStatus } from "../../api/client";
import { StatusBadge } from "../../components/StatusBadge";
import { Badge, cx } from "../../components/ui";
import { backlogVerdict, signature, type Verdict } from "./labels";

type Item = {
  status: GenerationStatus;
  stale?: unknown;
  current_approval?: Approval | null;
  approval_history?: Approval[];
};

/**
 * A backlog item's standing, on its card: the verdict first (what it needs from
 * a person), who signed when it is approved, and where the words came from.
 *
 * Provenance is shown only while the item is not approved: once someone has
 * signed, "Approved by …" says more than "Edited" does, and two badges both
 * claiming to be the status was the ambiguity the critique found.
 */
export function BacklogStatus({ item, level }: { item: Item; level: "epic" | "feature" | "story" }) {
  const verdict = backlogVerdict(item, level);
  const signed = signature(item);
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
      <Badge tone={verdict.tone}>{verdict.label}</Badge>
      {!signed && item.status !== "approved" && <StatusBadge status={item.status} />}
      {signed && <span className="text-meta text-ink-muted tabular-nums">{signed}</span>}
    </div>
  );
}

const GLYPH = { warning: TriangleAlert, success: Check } as const;

/**
 * The verdict in a row — the rail tree, the Feature list, the Story list. Words
 * and a glyph, never colour alone (design-system §4.5); a neutral verdict takes
 * no glyph so that the rows which need someone are the ones that stand out.
 */
export function VerdictText({ verdict, className }: { verdict: Verdict; className?: string }) {
  const Glyph = verdict.tone === "warning" || verdict.tone === "success" ? GLYPH[verdict.tone] : null;
  return (
    <span
      className={cx(
        "text-meta inline-flex items-center gap-1",
        verdict.tone === "warning" ? "text-warning" : verdict.tone === "success" ? "text-success" : "text-ink-muted",
        className,
      )}
    >
      {Glyph && <Glyph aria-hidden="true" className="shrink-0" size={13} />}
      {verdict.label}
    </span>
  );
}
