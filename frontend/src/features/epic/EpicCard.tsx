import { useState } from "react";

import type { Epic, EpicInput, FeatureSet, RequirementAnalysis } from "../../api/client";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { EditorConflictNotice } from "../../components/EditorConflictNotice";
import { ErrorNotice } from "../../components/ErrorNotice";
import { ProvenanceDetails } from "../../components/ProvenanceDetails";
import { StalenessNotice } from "../../components/StalenessNotice";
import { Button, Card, CardHeader } from "../../components/ui";
import type { ActionAvailability } from "../../api/client";
import { EpicEditForm } from "./EpicEditForm";
import { BacklogStatus } from "../breakdown/BacklogStatus";
import { useEditFocus } from "../breakdown/useEditFocus";

/**
 * The Epic — the top of the generated backlog.
 *
 * Two things carry the redesign here. The heading is an `h2`, because the page
 * `h1` is the requirement's own title (docs/ux-plan.md §4) and the Epic is the
 * subject of this route, not a third-level detail inside it. And the generated
 * prose — the outcome and the business case — is set in the document face, the
 * register docs/design-system.md §5 reserves for "requirement text, findings,
 * questions, generated narrative": a person can tell peripherally whether they
 * are reading the product or reading the draft.
 *
 * "More actions" is an inline disclosure and looks like one. It used to be a
 * `<details>` dressed as a dropdown, which pushed the card's content down on
 * open and answered neither Escape nor a click outside.
 *
 * Phase 4: approval is shown as the human act it is — the verdict, who signed
 * and when (the response always carried `current_approval`; the card never
 * showed it), and before signing, one line saying what the signature covers.
 * A gated Approve keeps its place in the tab order and says why.
 */
export function EpicCard({ epic, analysis, features, busy, error, canManage, onEdit, onApprove, onRegenerate, focused = false }: {
  focused?: boolean;
  epic: Epic;
  analysis: RequirementAnalysis | null;
  features: FeatureSet | null;
  busy: boolean;
  error: string | null;
  canManage: boolean;
  onEdit: (input: EpicInput, expectedVersion: number) => Promise<unknown> | void;
  onApprove: () => void;
  onRegenerate: (force: boolean) => void;
}) {
  const [editing, setEditing] = useState<Epic | null>(null);
  const [confirmation, setConfirmation] = useState<string | null>(null);
  // The server's own availability (ADR-0073): the browser no longer restates
  // the approval and generation rules. A missing analysis is a loading/absence
  // state the response cannot carry, so only that message is composed here.
  const approval = epic.actions.approve;
  const generation: ActionAvailability = analysis?.actions.generate_epic ?? {
    allowed: false,
    reason: "Analyse the current requirement before generating an Epic.",
    confirmation: null,
  };
  const { trigger, form } = useEditFocus(Boolean(editing));

  const regenerate = () => {
    const loss = epic.actions.regenerate.confirmation;
    if (loss) {
      // The child effect is display enrichment from data already on screen; the
      // decision that confirmation is needed at all is the server's.
      const count = features?.features.length ?? 0;
      const childEffect = count
        ? ` It will also mark ${count} Feature${count === 1 ? "" : "s"} out of date.`
        : "";
      setConfirmation(loss + childEffect);
    } else onRegenerate(false);
  };

  if (editing) {
    return (
      <div ref={form}><EditorConflictNotice baselineVersion={editing.version} currentVersion={epic.version} currentContent={[epic.name, epic.outcome, epic.business_case].join("\n\n")} onReconcile={() => setEditing(epic)} /><EpicEditForm
        epic={editing}
        busy={busy}
        error={error}
        onCancel={() => setEditing(null)}
        onSave={async (input) => { try { await onEdit(input, editing.version); setEditing(null); } catch { /* Mutation error remains visible with the draft. */ } }}
      /></div>
    );
  }

  // A reason whenever Approve cannot act, so the button keeps its tab stop and
  // explains itself instead of going natively dead.
  const approveReason = approval.allowed ? undefined : (approval.reason ?? undefined);

  const regenerateButton = (
    <Button disabled={!canManage || busy || !generation.allowed} onClick={regenerate}>
      {focused ? "Regenerate Epic" : "Regenerate"}
    </Button>
  );

  return (
    <Card as="article" className="epic-card" tone={epic.stale ? "warning" : "default"}>
      <CardHeader
        headingLevel="h2"
        title={epic.name}
        actions={
          <>
            <Button ref={trigger} disabled={!canManage || busy} onClick={() => setEditing(epic)}>Edit</Button>
            {focused ? (
              <details className="workspace-disclosure-inline">
                <summary>More actions</summary>
                <div className="mt-2 flex flex-wrap gap-2">{regenerateButton}</div>
              </details>
            ) : regenerateButton}
            {(!focused || epic.status !== "approved") && (
              <Button
                variant="primary"
                disabled={!canManage || busy}
                blockedReason={approveReason}
                onClick={onApprove}
              >
                {epic.status === "approved" ? "Approved" : "Approve"}
              </Button>
            )}
          </>
        }
      />

      <div className="mb-4 grid gap-2">
        <BacklogStatus item={epic} level="epic" />
        {/* What the signature covers, before the click rather than in a
            dialog after it: the most frequent act in the review stays one
            click, and nobody signs without reading what they sign. */}
        {canManage && approval.allowed && (
          <p className="text-meta text-ink-muted m-0 max-w-[var(--measure-document)]">
            Approving signs off this Epic as it reads now. Features are generated from it, and any later edit needs a new approval.
          </p>
        )}
      </div>

      {focused && !canManage && (
        <p className="text-ink-muted text-meta m-0 mb-3">
          You do not have permission to change this Requirement.
        </p>
      )}
      {!generation.allowed && <p className="text-ink-muted text-meta m-0 mb-3">{generation.reason}</p>}
      {epic.stale && <StalenessNotice stale={epic.stale} />}
      {error && <ErrorNotice message={error} />}

      {/* Two fields, stacked rather than columned: these are paragraphs, and a
          half-width column at this type size runs well under a readable
          measure the moment the rail is open beside it. */}
      <div className="grid gap-5">
        <div className="grid gap-1">
          <span className="text-label text-ink-muted">Outcome</span>
          <p className="text-document font-document text-ink-soft m-0 max-w-[var(--measure-document)]">
            {epic.outcome}
          </p>
        </div>
        <div className="grid gap-1">
          <span className="text-label text-ink-muted">Business case</span>
          <p className="text-document font-document text-ink-soft m-0 max-w-[var(--measure-document)]">
            {epic.business_case}
          </p>
        </div>
      </div>

      <ProvenanceDetails provenance={epic.provenance} />

      {confirmation && (
        <ConfirmDialog
          title="Replace this Epic?"
          message={confirmation}
          confirmLabel="Replace Epic"
          onCancel={() => setConfirmation(null)}
          onConfirm={() => { setConfirmation(null); onRegenerate(true); }}
        />
      )}
    </Card>
  );
}
