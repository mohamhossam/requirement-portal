import { Sparkles } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { Link } from "react-router-dom";

import type { EstimateSuggestion, FeatureEstimateSuggestions, Story, StoryEstimateInput } from "../../api/client";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { ErrorNotice } from "../../components/ErrorNotice";
import { ProvenanceDetails } from "../../components/ProvenanceDetails";
import { Button, Select } from "../../components/ui";
import { when } from "../breakdown/labels";
import { SizeBadge } from "./SizeBadge";
import {
  NOT_SIZED,
  STORY_POINT_SCALE,
  byRelativeSize,
  decidedBy,
  pointsLabel,
  reopenApproval,
  type SizeSibling,
} from "./storyPoints";

export type SizeChange = Pick<StoryEstimateInput, "points" | "basis">;

/**
 * How big a Story is, relative to its siblings (ADR-0121).
 *
 * The AI's size is a suggestion and says so — the spark glyph and the sunken
 * ground are the system's provenance register (§4.5), never a status. Only a
 * size a person confirms counts. Accepting is the one action because it is the
 * common case; another size is one step behind it, and saving is a button, so
 * moving through the options never records anything.
 *
 * Points mean something only beside the other Stories, so while a decision is
 * open the siblings are listed with their sizes. Once a person has decided, a
 * different AI number is history, not a call to action: it shrinks to one line.
 *
 * Focus never falls to the page: opening the picker moves it to the select,
 * Cancel and a save return it to the heading, and the result is announced.
 */
export function StorySizePanel({
  story,
  suggestion,
  suggestionStale = false,
  provenance,
  siblings = [],
  busy,
  error,
  disabled,
  describedBy,
  canSuggest,
  suggesting,
  onSuggest,
  onSplit,
  onSize,
  returnHref,
}: {
  story: Story;
  /** This Story's current suggestion; null when there is none or it is out of date. */
  suggestion: EstimateSuggestion | null;
  /** Suggestions exist for the Feature but were made for different Story content. */
  suggestionStale?: boolean;
  provenance: FeatureEstimateSuggestions["provenance"] | null;
  /** The other Stories in the Feature, for comparison. */
  siblings?: SizeSibling[];
  busy: boolean;
  error: string | null;
  /** Changing the size is not allowed right now; `describedBy` says why. */
  disabled: boolean;
  /** The id of the line that says why, when it is on screen. */
  describedBy?: string;
  canSuggest: boolean;
  suggesting: boolean;
  onSuggest: () => void;
  /** Ask the AI for a split, for a Story too large to size. */
  onSplit?: () => void;
  onSize: (change: SizeChange) => void;
  /** Where the person came from to size this Story (Review & approve), so there is a way back. */
  returnHref?: string;
}) {
  const headingId = useId();
  const rationaleId = useId();
  const headingRef = useRef<HTMLHeadingElement>(null);
  const selectRef = useRef<HTMLSelectElement>(null);
  const awaitingSave = useRef(false);

  const estimate = story.estimate ?? null;
  const current = estimate?.points ?? null;
  // A suggestion only matters while it would change something.
  const differing =
    suggestion != null && (suggestion.points == null ? current == null : suggestion.points !== current)
      ? suggestion
      : null;
  // Unsized, it is the decision on offer; sized, it is a footnote to the person's call.
  const offered = estimate ? null : differing;
  const overridden = estimate ? differing : null;
  const acceptable = offered?.points ?? null;
  const startingChoice = String(current ?? acceptable ?? "");

  const [editing, setEditing] = useState(false);
  const [choice, setChoice] = useState(startingChoice);
  const [pending, setPending] = useState<"accept" | "save" | null>(null);
  const [confirming, setConfirming] = useState<SizeChange | null>(null);
  const [announcement, setAnnouncement] = useState("");
  // A saved size arrives as a new Story version: close the form and say what changed.
  const [seen, setSeen] = useState({ version: story.version, points: current });
  if (seen.version !== story.version) {
    setSeen({ version: story.version, points: current });
    setEditing(false);
    setPending(null);
    setChoice(startingChoice);
    if (seen.points !== current) {
      setAnnouncement(current == null ? "Size cleared." : `Size set to ${pointsLabel(current)}.`);
    }
  }
  useEffect(() => {
    if (!awaitingSave.current) return;
    awaitingSave.current = false;
    headingRef.current?.focus();
  }, [story.version]);
  // A failed save leaves no version change to wait for.
  useEffect(() => {
    if (error) awaitingSave.current = false;
  }, [error]);
  useEffect(() => {
    if (editing) selectRef.current?.focus();
  }, [editing]);
  // Sent here to size this Story: start at the question, not the top of the page.
  useEffect(() => {
    const heading = headingRef.current;
    if (!returnHref || !heading) return;
    heading.focus({ preventScroll: true });
    const place = () => heading.scrollIntoView({ block: "center" });
    place();
    if (typeof ResizeObserver === "undefined") return;
    // What sits above the question (readiness checks, system impact) can still be
    // loading and push it down; keep it in view until the page settles or the
    // person takes over.
    const observer = new ResizeObserver(place);
    observer.observe(document.body);
    const stop = () => observer.disconnect();
    const timer = window.setTimeout(stop, 1500);
    const events = ["wheel", "keydown", "pointerdown", "touchstart"] as const;
    for (const name of events) window.addEventListener(name, stop, { once: true, passive: true });
    return () => {
      stop();
      window.clearTimeout(timer);
      for (const name of events) window.removeEventListener(name, stop);
    };
  }, [returnHref]);

  const chosen = choice === "" ? null : Number(choice);
  const blocked = disabled || busy;
  // Gated, not disabled, where the reason is on screen: the control keeps its tab
  // stop and is described by that line (§11).
  const gate = (extra = false) =>
    disabled && describedBy ? { blockedBy: describedBy } : { disabled: disabled || extra };

  const commit = (change: SizeChange, action: "accept" | "save") => {
    setPending(action);
    awaitingSave.current = true;
    onSize(change);
  };
  const request = (change: SizeChange, action: "accept" | "save") => {
    if (story.status === "approved") setConfirming(change);
    else commit(change, action);
  };
  const startEditing = () => {
    setChoice(startingChoice);
    setEditing(true);
  };
  const stopEditing = () => {
    setEditing(false);
    headingRef.current?.focus();
  };

  // This Story placed among its siblings, smallest first: a ladder to read a size
  // against, not a list to remember.
  const ladder = byRelativeSize([
    ...siblings,
    { id: story.id, gist: "This Story", points: current, suggested: suggestion?.points ?? null },
  ]);
  const comparison = siblings.length > 0 && (editing || !estimate) && (
    <div className="grid gap-1">
      <p className="text-meta text-ink-muted m-0">The Stories in this Feature, smallest first:</p>
      <ol className="m-0 grid list-none gap-0.5 p-0">
        {ladder.map((item) => (
          <li
            key={item.id}
            aria-current={item.id === story.id ? "true" : undefined}
            className={item.id === story.id ? "text-meta text-ink max-w-[68ch] font-semibold" : "text-meta text-ink-soft max-w-[68ch]"}
          >
            {item.gist}
            <span className="text-ink-muted">
              {" — "}
              {item.points != null
                ? pointsLabel(item.points)
                : item.suggested != null
                  ? `AI suggests ${pointsLabel(item.suggested)}`
                  : NOT_SIZED}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );

  return (
    <section aria-labelledby={headingId} className="mt-5 grid gap-3">
      <div className="grid gap-0.5">
        <h3 ref={headingRef} tabIndex={-1} id={headingId} className="text-title text-ink m-0">
          How big is this Story, compared with the others?
        </h3>
        <p className="text-meta text-ink-muted m-0 max-w-[60ch]">
          Size is relative effort against the other Stories in this Feature, in story points — not
          hours or days.
        </p>
      </div>
      <p role="status" className="sr-only">{announcement}</p>
      {returnHref && (
        <Link className="text-meta text-ink-soft hover:text-ink w-fit underline underline-offset-2" to={returnHref}>
          Back to Review &amp; approve
        </Link>
      )}

      {estimate && !editing && (
        <div className="grid gap-1">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <SizeBadge points={estimate.points} />
            <span className="text-meta text-ink-muted">
              {decidedBy(estimate.basis, estimate.decided_by.display_name)}
              {" · "}
              {when(estimate.decided_at)}
            </span>
            <Button variant="text" {...gate(busy)} onClick={startEditing}>
              Change size
            </Button>
          </div>
          {overridden && (
            <details className="workspace-disclosure-inline text-meta text-ink-muted">
              <summary>
                {overridden.points != null
                  ? `The AI suggested ${pointsLabel(overridden.points)}`
                  : "The AI could not size it"}
              </summary>
              <p className="font-document text-document text-ink-soft m-0 mt-1 max-w-[var(--measure-document)] leading-[1.6]">
                {overridden.rationale}
              </p>
            </details>
          )}
        </div>
      )}

      {offered && !editing && (
        <div className="bg-surface-sunken grid gap-1 rounded-sm p-3">
          <p className="text-title text-ink m-0 flex items-center gap-2 font-semibold">
            <Sparkles aria-hidden="true" className="text-ink-muted shrink-0" size={16} />
            {acceptable != null
              ? `AI suggests ${pointsLabel(acceptable)}`
              : "The AI could not size this Story"}
          </p>
          <p
            id={rationaleId}
            className="font-document text-document text-ink-soft m-0 max-w-[var(--measure-document)] leading-[1.6]"
          >
            {offered.rationale}
          </p>
          <small className="text-meta text-ink-muted">
            {acceptable != null
              ? "AI judgement — a suggestion until someone accepts it. Accepting marks the Story Edited."
              : "AI judgement — choose a size yourself, or split the Story first"}
          </small>
          <div className="mt-2 flex flex-wrap items-center gap-3">
            {acceptable != null && (
              <Button
                {...gate(busy)}
                aria-describedby={rationaleId}
                loading={busy && pending === "accept"}
                loadingLabel="Saving…"
                onClick={() => request({ points: acceptable, basis: "accepted_suggestion" }, "accept")}
              >
                Accept {pointsLabel(acceptable)}
              </Button>
            )}
            {acceptable == null && onSplit && (
              <Button {...gate(busy)} onClick={onSplit}>Suggest a split</Button>
            )}
            <Button variant="text" {...gate(busy)} onClick={startEditing}>
              {acceptable != null ? "Choose another size" : "Choose a size"}
            </Button>
          </div>
        </div>
      )}

      {!estimate && !offered && !editing && (
        <div className="grid gap-2">
          <p className="text-body text-ink-soft m-0">
            {NOT_SIZED}.{" "}
            {suggestionStale
              ? "The earlier suggestion was made before these Stories changed."
              : "There is no suggestion for it yet."}
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              {...(!canSuggest && describedBy ? { blockedBy: describedBy } : { disabled: !canSuggest })}
              loading={suggesting}
              loadingLabel="Suggesting sizes…"
              onClick={onSuggest}
            >
              {suggestionStale ? "Suggest sizes again" : "Suggest sizes"}
            </Button>
            <Button variant="text" {...gate(busy)} onClick={startEditing}>
              Choose a size
            </Button>
          </div>
        </div>
      )}

      {editing && (
        <form
          className="grid gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            // Choosing the AI's own number is accepting it, whichever control did it.
            const accepted = chosen != null && suggestion?.points === chosen;
            request(
              { points: chosen, basis: accepted ? "accepted_suggestion" : "team_entered" },
              "save",
            );
          }}
        >
          {/* The AI's reasoning stays in view while a person decides against it. */}
          {suggestion && (
            <p className="text-meta text-ink-muted m-0 flex max-w-[68ch] items-start gap-1.5">
              <Sparkles aria-hidden="true" className="mt-0.5 shrink-0" size={12} />
              <span>
                {suggestion.points != null
                  ? `The AI suggested ${pointsLabel(suggestion.points)}: `
                  : "The AI could not size it: "}
                {suggestion.rationale}
              </span>
            </p>
          )}
          <Select
            ref={selectRef}
            label="Size in story points"
            hint="13 is the largest size; anything bigger should be split first. Saving a size marks the Story Edited."
            fieldClassName="max-w-[16rem]"
            value={choice}
            disabled={blocked}
            aria-describedby={disabled ? describedBy : undefined}
            onChange={(event) => setChoice(event.target.value)}
          >
            <option value="">{NOT_SIZED}</option>
            {STORY_POINT_SCALE.map((points) => (
              <option key={points} value={points}>
                {pointsLabel(points)}
                {suggestion?.points === points ? " (AI suggestion)" : ""}
              </option>
            ))}
          </Select>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              type="submit"
              {...gate(busy || chosen === current)}
              loading={busy && pending === "save"}
              loadingLabel="Saving…"
            >
              {chosen == null && current != null ? "Clear size" : "Save size"}
            </Button>
            <Button variant="text" onClick={stopEditing}>Cancel</Button>
          </div>
        </form>
      )}

      {comparison}

      {error && <ErrorNotice message={error} />}
      {offered && provenance && (
        <ProvenanceDetails label="How this size suggestion was generated" provenance={provenance} />
      )}

      {confirming && (
        <ConfirmDialog
          {...reopenApproval(current, confirming.points ?? null)}
          confirmTone="primary"
          onCancel={() => setConfirming(null)}
          onConfirm={() => {
            const change = confirming;
            setConfirming(null);
            commit(change, change.basis === "accepted_suggestion" ? "accept" : "save");
          }}
        />
      )}
    </section>
  );
}
