import { useState } from "react";

import type { Story, StoryInput, StoryQuality } from "../../api/client";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { CriterionLines } from "./CriterionLines";
import { EditorConflictNotice } from "../../components/EditorConflictNotice";
import { ErrorNotice } from "../../components/ErrorNotice";
import { ProvenanceDetails } from "../../components/ProvenanceDetails";
import { StalenessNotice } from "../../components/StalenessNotice";
import { Disclosure } from "../../components/Disclosure";
import { Link } from "react-router-dom";

import { Button, Card, Checkbox } from "../../components/ui";
import { storyRegenerationLoss } from "../../review/rules";
import { ArchitectureImpactPanel } from "../architecture/ArchitectureImpactPanel";
import { StoryEditForm } from "./StoryEditForm";
import { StoryQualityPanel } from "./StoryQualityPanel";
import { BacklogStatus } from "../breakdown/BacklogStatus";
import { useEditFocus } from "../breakdown/useEditFocus";

/**
 * One User Story, and the deepest thing a reviewer reads.
 *
 * Everything the model wrote is in the document face: the voice, and every
 * Given / When / Then. That is the whole point of docs/design-system.md §5's
 * register split — "a person can tell peripherally whether they are looking at
 * the product or at the requirement" — and the backlog was the one place still
 * setting generated prose in the interface face at 0.82rem.
 *
 * The ordinal gutter is gone for the same reason it went from the Feature: a
 * Story's position in its set is not information a reviewer acts on, and it was
 * spending 2.4rem of the narrowest column on the screen.
 *
 * Phase 4: the card no longer spends the accent on "Continue reviewing", a
 * filled link out to Review & approve on every Story. The way forward is the
 * pager above the card; this card says where it stands — out of date, or who
 * approved it and when — and that Stories are approved on Review & approve,
 * which is why there is no Approve here.
 */
export function StoryCard({
  story,
  busy,
  error,
  selected,
  onToggleSelect,
  onEdit,
  onRegenerate,
  onSplit,
  onManualSplit,
  disabledReason,
  quality,
  focused = false,
  reviewHref,
}: {
  story: Story;
  /** Kept for the non-focused tree; the card no longer renders an ordinal. */
  position: number;
  busy: boolean;
  error: string | null;
  selected: boolean;
  onToggleSelect: () => void;
  onEdit: (input: StoryInput, expectedVersion: number) => Promise<unknown> | void;
  onRegenerate: (force: boolean) => void;
  onSplit: () => void;
  onManualSplit: () => void;
  disabledReason: string | null;
  quality: StoryQuality | null;
  focused?: boolean;
  reviewHref?: string;
}) {
  const [editing, setEditing] = useState<Story | null>(null);
  const [confirmation, setConfirmation] = useState<string | null>(null);
  const { trigger, form } = useEditFocus(Boolean(editing));

  const regenerate = () => {
    const loss = storyRegenerationLoss(story);
    if (loss) setConfirmation(loss);
    else onRegenerate(false);
  };

  const gated = busy || Boolean(disabledReason);
  const reasonId = `story-${story.id}-gated`;
  const moreActions = (
    <>
      <Button disabled={gated} aria-describedby={disabledReason ? reasonId : undefined} onClick={regenerate}>
        {focused ? "Regenerate Story" : "Regenerate"}
      </Button>
      <Button disabled={gated} aria-describedby={disabledReason ? reasonId : undefined} onClick={onManualSplit}>Split by hand</Button>
      <Button disabled={gated} aria-describedby={disabledReason ? reasonId : undefined} onClick={onSplit}>Suggest a split</Button>
    </>
  );

  if (editing) {
    return (
      <div ref={form}><EditorConflictNotice baselineVersion={editing.version} currentVersion={story.version} currentContent={story.voice} onReconcile={() => setEditing(story)} /><StoryEditForm
        story={editing}
        busy={busy}
        error={error}
        onCancel={() => setEditing(null)}
        onSave={async (input) => { try { await onEdit(input, editing.version); setEditing(null); } catch { /* Mutation error remains visible with the draft. */ } }}
      /></div>
    );
  }

  const Voice = focused ? "h2" : "p";

  return (
    <Card
      as="article"
      className="story-card"
      id={`story-${story.id}`}
      tone={story.stale ? "warning" : "default"}
    >
      <header className="mb-4 grid gap-3">
        {/* Meta and controls share the top row; the voice gets the one below to
            itself. It is a sentence at the document measure, so sitting it
            beside the actions pushed them onto a second line on every Story. */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <BacklogStatus item={story} level="story" />
            {focused && quality && (
              <span className="text-ink-muted text-meta">
                {quality.status === "passes"
                  ? "Quality checks passed"
                  : `${quality.failure_count} quality concern${quality.failure_count === 1 ? "" : "s"}`}
              </span>
            )}
          </div>
          {/* `min-w-0`, not `shrink-0`: at 390px the three controls were wider
              than the card and pushed the page to 397px. Now they wrap. */}
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <Button ref={trigger} disabled={gated} aria-describedby={disabledReason ? reasonId : undefined} onClick={() => setEditing(story)}>Edit</Button>
            {focused ? (
              <details className="workspace-disclosure-inline">
                <summary>More actions</summary>
                <div className="mt-2 flex flex-wrap gap-2">{moreActions}</div>
              </details>
            ) : moreActions}
          </div>
        </div>
        <Voice className="font-document text-document-lead text-ink m-0 max-w-[var(--measure-document)] leading-[1.55] font-semibold">
          {story.voice}
        </Voice>
        {focused && disabledReason && (
          <p className="text-meta text-ink-muted m-0" id={reasonId}>{disabledReason}</p>
        )}
        {focused && reviewHref && story.status !== "approved" && !story.stale && (
          <p className="text-meta text-ink-muted m-0">
            Stories are approved on{" "}
            <Link className="text-ink-soft hover:text-ink underline underline-offset-2" to={reviewHref}>
              Review &amp; approve
            </Link>
            , not here.
          </p>
        )}
        {!focused && (
          <Checkbox
            label="Select to merge"
            checked={selected}
            disabled={Boolean(disabledReason)}
            onChange={onToggleSelect}
          />
        )}
      </header>

      {story.stale && <StalenessNotice stale={story.stale} />}
      {error && <ErrorNotice message={error} />}

      <div className="grid gap-2">
        <h3 className="text-label text-ink-muted m-0">Acceptance criteria</h3>
        <ol className="border-line m-0 grid list-none gap-3 border-0 border-l border-solid p-0 pl-4">
          {story.acceptance_criteria.map((criterion, index) => (
            <li key={index} className="grid gap-0.5">
              <CriterionLines criterion={criterion} />
            </li>
          ))}
        </ol>
      </div>

      {focused ? (
        <Disclosure label="System impact">
          <ArchitectureImpactPanel impact={story.architecture} compact />
        </Disclosure>
      ) : (
        <ArchitectureImpactPanel impact={story.architecture} compact />
      )}

      {quality && <StoryQualityPanel quality={quality} focused={focused} />}
      <ProvenanceDetails provenance={story.provenance} />

      {confirmation && (
        <ConfirmDialog
          title="Replace this Story?"
          message={confirmation}
          confirmLabel="Replace Story"
          onCancel={() => setConfirmation(null)}
          onConfirm={() => { setConfirmation(null); onRegenerate(true); }}
        />
      )}
    </Card>
  );
}
