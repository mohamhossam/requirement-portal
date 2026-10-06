import type { IntentProposal, IntentProposalStatus, RequirementAnalysis } from "../../api/client";
import { Badge, Button, Card, Textarea } from "../../components/ui";
import { SourceLinks } from "./AnalysisSources";
import { humanEvidence } from "./analysisFormat";
import { INTENT_KIND_LABEL, PROPOSAL_STATUS_LABEL } from "./labels";
import { passageHref } from "../../api/knowledge";
import { ReviewOverdue } from "../../components/ReviewOverdue";

export type IntentProposalDraft = { version: number; replacement: string; measures: string; rationale?: string };

/**
 * One AI intent proposal, with its decision.
 *
 * Rendered in the open column while it is pending and in the settled column
 * once it is decided, which is the whole thesis of the screen applied to the
 * one piece of content that genuinely moves between the two.
 */
export function IntentProposalCard({
  analysis,
  proposal,
  busy,
  canDecide,
  permissionReason,
  draft,
  onDraft,
  onCloseDraft,
  onDecide,
}: {
  analysis: RequirementAnalysis;
  proposal: IntentProposal;
  busy: boolean;
  canDecide: boolean;
  permissionReason?: string;
  draft?: IntentProposalDraft;
  onDraft: (change: Partial<Pick<IntentProposalDraft, "replacement" | "measures" | "rationale">>) => void;
  onCloseDraft: () => void;
  onDecide?: (
    proposal: IntentProposal,
    decision: IntentProposalStatus,
    replacement?: string,
    successMeasures?: string[],
    rationale?: string,
  ) => void;
}) {
  const persistedReplacement = proposal.effective_statement ?? proposal.statement;
  const effectiveMeasures = proposal.effective_success_measures.length
    ? proposal.effective_success_measures
    : proposal.success_measures;
  const persistedMeasures = effectiveMeasures.join("\n");
  const replacement = draft?.replacement ?? persistedReplacement;
  const measures = draft?.measures ?? persistedMeasures;
  const resolvedMeasures = measures
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
  const hasChanges =
    replacement.trim() !== persistedReplacement ||
    resolvedMeasures.join("\n") !== effectiveMeasures.join("\n");
  const editing = !analysis.human_confirmed && (proposal.status === "pending" || draft !== undefined);
  const decided = proposal.status !== "pending";
  const references = proposal.reference_evidence ?? [];
  const stale = (analysis.stale_reference_proposal_ids ?? []).includes(proposal.id);
  const rationale = draft?.rationale ?? "";
  const missingRationale = references.length > 0 && !rationale.trim();
  const decide = (decision: IntentProposalStatus, wording?: string, success?: string[]) => {
    if (references.length) onDecide?.(proposal, decision, wording, success, rationale.trim());
    else if (decision === "edited") onDecide?.(proposal, decision, wording, success);
    else onDecide?.(proposal, decision);
  };

  return (
    <Card
      className="grid scroll-mb-20 gap-3 p-4"
      tone={
        proposal.status === "rejected"
          ? "default"
          : proposal.status === "pending"
            ? "warning"
            : "success"
      }
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Badge tone="neutral">{INTENT_KIND_LABEL[proposal.kind]}</Badge>
        <Badge
          tone={
            proposal.status === "pending"
              ? "warning"
              : proposal.status === "rejected"
                ? "neutral"
                : "success"
          }
        >
          {PROPOSAL_STATUS_LABEL[proposal.status]}
        </Badge>
      </div>

      <p className="text-document text-ink m-0 max-w-[68ch] font-serif">{proposal.statement}</p>
      {proposal.rationale && (
        <p className="text-ink-muted text-body m-0 max-w-[68ch]">{proposal.rationale}</p>
      )}
      {references.length > 0 && (
        <section aria-label="Reference applicability" className="grid min-w-0 gap-2">
          <h4 className="text-label m-0">Reference applicability — {stale ? "reconciliation required" : editing || !decided ? "owner decision required" : "owner decision recorded"}</h4>
          {proposal.reference_conflict && (editing || !decided) && <p className="text-body m-0">Conflicting evidence: decide which source applies and explain why.</p>}
          {stale && <p role="alert" className="text-body m-0">Reference evidence changed. Re-analyse, then reject the outdated proposal or review a new citation before continuing.</p>}
          {references.map((citation) => (
            <div key={`${citation.publication_id}:${citation.block_id}:${citation.start_offset}`} className="grid min-w-0 gap-1">
              <a className="text-accent text-body break-words underline" target="_blank" rel="noreferrer" href={passageHref(citation)}>
                <bdi>{citation.title}</bdi> · version {citation.version_number} · <bdi>{citation.location}</bdi>
              </a>
              <blockquote dir="auto" className="text-document m-0 whitespace-pre-wrap break-words font-serif">{citation.excerpt}</blockquote>
              <ReviewOverdue dueOn={analysis.overdue_reference_reviews?.[citation.document_id]} subject="document" />
            </div>
          ))}
          {proposal.reference_provenance && <p className="text-meta text-ink-muted m-0">Proposal generated by {proposal.reference_provenance.model} · {proposal.reference_provenance.prompt_version}</p>}
        </section>
      )}
      <SourceLinks
        evidence={proposal.evidence_references}
        humanAnswers={humanEvidence(analysis, "intent_proposal", proposal.statement)}
        subject={proposal.statement}
      />

      {editing && (
        <>
          {references.length > 0 && <Textarea label="Applicability rationale" hint="Required for acceptance, edited wording or rejection. Explain why this evidence does or does not apply." disabled={busy || !canDecide} maxLength={2000} rows={2} value={rationale} onChange={(event) => onDraft({ rationale: event.target.value })} />}
          <Textarea
            disabled={busy || !canDecide}
            label="Your wording"
            onChange={(event) => onDraft({ replacement: event.target.value })}
            rows={3}
            value={replacement}
          />
          {proposal.kind === "desired_outcome" && (
            <Textarea
              disabled={busy || !canDecide}
              hint="One per line."
              label="How you would know it worked"
              onChange={(event) => onDraft({ measures: event.target.value })}
              rows={3}
              value={measures}
            />
          )}
          <div className="flex flex-wrap gap-2">
            <Button
              disabled={busy || !canDecide || missingRationale || stale || proposal.status === "accepted"}
              blockedReason={canDecide ? undefined : permissionReason}
              onClick={() => decide("accepted")}
              variant="primary"
            >
              Accept as written
            </Button>
            <Button
              disabled={busy || !canDecide || missingRationale || stale || !replacement.trim() || !hasChanges}
              onClick={() =>
                decide("edited", replacement.trim(), resolvedMeasures)
              }
            >
              Save my wording
            </Button>
            <Button
              disabled={busy || !canDecide || missingRationale || proposal.status === "rejected"}
              blockedReason={undefined}
              onClick={() => decide("rejected")}
              variant="danger"
            >
              Reject
            </Button>
            {decided && (
              <Button disabled={busy} onClick={onCloseDraft} variant="ghost">
                Cancel
              </Button>
            )}
          </div>
        </>
      )}

      {decided && !editing && (
        <div className="grid gap-2">
          {proposal.status === "rejected" ? (
            <p className="text-ink-muted text-body m-0">
              This is not part of what the requirement is trying to achieve.
            </p>
          ) : (
            <>
              <div className="grid gap-1">
                <span className="text-label text-ink-muted">Agreed wording</span>
                <span className="text-document text-ink font-serif">{persistedReplacement}</span>
              </div>
              {proposal.kind === "desired_outcome" && effectiveMeasures.length > 0 && (
                <div className="grid gap-1">
                  <span className="text-label text-ink-muted">How we will know it worked</span>
                  <ul className="text-document text-ink-soft grid list-disc gap-1 pl-5 font-serif">
                    {effectiveMeasures.map((measure) => (
                      <li key={measure}>{measure}</li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}
          {!analysis.human_confirmed && (
            <Button
              blockedReason={canDecide ? undefined : permissionReason}
              disabled={busy}
              onClick={() =>
                onDraft({ replacement: persistedReplacement, measures: persistedMeasures })
              }
              size="sm"
              variant="text"
            >
              Change this decision
            </Button>
          )}
        </div>
      )}

      {proposal.decisions.length > 0 && (
        <p className="text-ink-muted text-meta m-0">
          Last decided by {proposal.decisions.at(-1)?.decided_by.display_name}.
          {proposal.decisions.at(-1)?.rationale && <> Rationale: <bdi>{proposal.decisions.at(-1)?.rationale}</bdi></>}
        </p>
      )}
    </Card>
  );
}
