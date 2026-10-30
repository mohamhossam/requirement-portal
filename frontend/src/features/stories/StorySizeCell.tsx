import { Sparkles } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

import type { EstimateSuggestion, Story } from "../../api/client";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Button } from "../../components/ui";
import { SizeBadge } from "./SizeBadge";
import type { SizeChange } from "./StorySizePanel";
import { NOT_SIZED, decidedBy, pointsLabel, reopenApproval } from "./storyPoints";
import { storyGist } from "./storyVoice";

/**
 * A Story's size on its row in the Feature's list (ADR-0121).
 *
 * Points are relative, so the list is where they are decided: every sibling and
 * its size or suggestion in one view, and the common act — accepting the AI's
 * number — one click on the row. The reason is a quiet "Why?" that opens below
 * the row, so the decision never moves while it is being read.
 *
 * The row carries its own outcome: a failed save is said here, a successful one
 * is announced, and focus lands on the new size instead of falling to the page.
 */
export function StorySizeCell({
  story,
  suggestion,
  busy,
  error,
  disabled,
  describedBy,
  onSize,
}: {
  story: Story;
  /** The current suggestion for this Story; null when there is none or it is out of date. */
  suggestion: EstimateSuggestion | null;
  busy: boolean;
  /** Why the last size change for this Story failed. */
  error: string | null;
  disabled: boolean;
  describedBy?: string;
  onSize: (change: SizeChange) => void;
}) {
  const reasonId = useId();
  const sizeRef = useRef<HTMLSpanElement>(null);
  const awaitingSave = useRef(false);
  const [confirming, setConfirming] = useState(false);
  const [showReason, setShowReason] = useState(false);
  const [announcement, setAnnouncement] = useState("");
  const estimate = story.estimate ?? null;
  const points = estimate?.points ?? null;
  const gist = storyGist(story.voice);

  const [seen, setSeen] = useState({ version: story.version, points });
  if (seen.version !== story.version) {
    setSeen({ version: story.version, points });
    if (seen.points !== points && points != null) {
      setAnnouncement(`Size set to ${pointsLabel(points)} for ${gist.replace(/\.$/, "")}.`);
    }
  }
  useEffect(() => {
    if (!awaitingSave.current) return;
    awaitingSave.current = false;
    sizeRef.current?.focus();
  }, [story.version]);
  useEffect(() => {
    if (error) awaitingSave.current = false;
  }, [error]);

  const suggested = estimate ? null : (suggestion?.points ?? null);
  const accept = () => {
    if (suggested == null) return;
    awaitingSave.current = true;
    onSize({ points: suggested, basis: "accepted_suggestion" });
  };

  let body;
  if (estimate) {
    body = (
      // Focus lands here after an accept, so the person stays on the row they acted on.
      <span ref={sizeRef} tabIndex={-1} className="flex flex-wrap items-center gap-x-2 gap-y-1 rounded-xs">
        <SizeBadge points={estimate.points} />
        <span className="text-meta text-ink-muted">
          {decidedBy(estimate.basis, estimate.decided_by.display_name)}
        </span>
      </span>
    );
  } else if (!suggestion) {
    body = <span className="text-meta text-ink-muted">{NOT_SIZED}</span>;
  } else if (suggested == null) {
    body = <span className="text-meta text-ink-muted">{NOT_SIZED} · the AI could not size it</span>;
  } else {
    body = (
      <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="text-meta text-ink-soft flex items-center gap-1.5">
          <Sparkles aria-hidden="true" className="text-ink-muted shrink-0" size={12} />
          AI suggests {pointsLabel(suggested)}
        </span>
        <Button
          size="sm"
          {...(disabled && describedBy ? { blockedBy: describedBy } : { disabled: disabled || busy })}
          loading={busy}
          loadingLabel="Saving…"
          // Starts with the visible label (WCAG 2.5.3), then says which Story.
          aria-label={`Accept ${pointsLabel(suggested)}: ${gist}`}
          onClick={() => (story.status === "approved" ? setConfirming(true) : accept())}
        >
          Accept {pointsLabel(suggested)}
        </Button>
        <Button
          variant="text"
          aria-expanded={showReason}
          aria-controls={reasonId}
          onClick={() => setShowReason((open) => !open)}
        >
          Why?
        </Button>
      </span>
    );
  }

  return (
    <div className="grid gap-2">
      {body}
      {suggestion && suggested != null && (
        <p
          id={reasonId}
          hidden={!showReason}
          className="font-document text-document text-ink-soft m-0 max-w-[var(--measure-document)] leading-[1.6]"
        >
          {suggestion.rationale}
        </p>
      )}
      <span role="status" className="sr-only">{announcement}</span>
      {error && <ErrorNotice message={`The size for this Story was not saved: ${error}`} />}
      {confirming && (
        <ConfirmDialog
          {...reopenApproval(points, suggested)}
          confirmTone="primary"
          onCancel={() => setConfirming(false)}
          onConfirm={() => {
            setConfirming(false);
            accept();
          }}
        />
      )}
    </div>
  );
}
