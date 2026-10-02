import { Sparkles } from "lucide-react";
import { CriterionLines } from "./CriterionLines";

import { StoryQualityPanel } from "./StoryQualityPanel";
import type { StoryProposal } from "../../api/client";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Badge, Button, Card } from "../../components/ui";

/**
 * A split or merge the model suggested, waiting on a person.
 *
 * Phase 4 moved it off the retired `.proposal-*` rules (8px and 0.7rem radii)
 * and the uppercase "AI proposal" eyebrow above its heading. Who wrote it is now
 * said the way provenance is said everywhere else — a glyph and a label on a
 * badge (design-system §4.5) — and the suggested Stories are set in the
 * document face, because they are drafted prose, not the interface.
 */
export function StoryProposalPanel({
  proposal,
  busy,
  error,
  onApply,
  onDiscard,
}: {
  proposal: StoryProposal;
  busy: boolean;
  error: string | null;
  onApply: () => void;
  onDiscard: () => void;
}) {
  const verb = proposal.operation === "split" ? "Split" : "Merge";
  const count = proposal.candidates.length;
  return (
    <Card as="section" padding="snug" className="grid gap-4" aria-label={`Pending ${proposal.operation} proposal`}>
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="grid gap-1.5">
          <Badge icon={<Sparkles aria-hidden={true} className="shrink-0" size={12} />}>
            Suggested by AI — read it before applying
          </Badge>
          <h4 className="text-title text-ink m-0">
            {verb} into {count} Stor{count === 1 ? "y" : "ies"}
          </h4>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="secondary" type="button" disabled={busy} onClick={onDiscard}>
            Discard
          </Button>
          <Button variant="primary" type="button" disabled={busy} onClick={onApply}>
            Apply proposal
          </Button>
        </div>
      </header>
      {error && <ErrorNotice message={error} />}
      <ol className="m-0 grid list-none gap-3 p-0">
        {proposal.candidates.map((candidate, index) => (
          <li key={index} className="border-line bg-surface-sunken grid gap-3 rounded-md border border-solid p-4">
            <p className="text-document font-document text-ink m-0 max-w-[var(--measure-document)] font-semibold">
              {candidate.voice}
            </p>
            {candidate.quality && <StoryQualityPanel quality={candidate.quality} />}
            <ol className="border-line m-0 grid list-none gap-3 border-0 border-l border-solid p-0 pl-4">
              {candidate.acceptance_criteria.map((criterion, criterionIndex) => (
                <li key={criterionIndex} className="grid gap-0.5">
                  <CriterionLines criterion={criterion} />
                </li>
              ))}
            </ol>
          </li>
        ))}
      </ol>
    </Card>
  );
}
