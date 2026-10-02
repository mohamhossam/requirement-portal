import { Link } from "react-router-dom";

import type { Requirement, RequirementAnalysis } from "../../api/client";
import { errorMessage } from "../../api/errors";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { Button } from "../../components/ui/Button";
import { DocumentPanel } from "../../features/documents/DocumentPanel";
import { RequirementForm } from "../../features/requirement/RequirementForm";
import type { WorkspaceChange } from "../workspaceInvalidation";
import { RequirementFacts } from "./RequirementFacts";
import type { SourceEditing } from "./useSourceEditing";

/**
 * The original requirement, one button away on every stage.
 *
 * It used to be a sticky rail on six routes and the contents of a drawer on the
 * seventh — two implementations of one panel, which docs/ux-plan.md §3.3 counts
 * among the reasons Backlog read as a different application. Now it is the drawer
 * everywhere (§4, "panels, not stage-dependent shapeshifting"), which is also
 * what makes it work at 375px: a 280px rail beside a question list does not.
 *
 * Named `SourcePanel` rather than `SourceRail` because it is no longer a rail.
 */
export function SourcePanel({
  id,
  requirement,
  analysis,
  canGovern,
  source,
  refresh,
}: {
  id: string;
  requirement: Requirement;
  analysis: RequirementAnalysis | null;
  canGovern: boolean;
  source: SourceEditing;
  refresh: (change: WorkspaceChange) => Promise<unknown>;
}) {
  return (
    // The drawer's own heading already says "Source document"; a second title
    // and the full UUID under it were two more lines before the business need.
    <section className="grid gap-4" aria-label="Original requirement">
      <div className="grid gap-4">
        {source.editing && canGovern ? (
          <RequirementForm
            initial={{
              title: requirement.title,
              description: requirement.description,
              desired_outcome: requirement.desired_outcome,
              customer_context: requirement.customer_context,
              channels: requirement.channels,
              systems: requirement.systems,
              business_rules: requirement.business_rules,
              constraints: requirement.constraints,
            }}
            hasIncludedAttachment={source.attachments.hasIncludedAttachment}
            attachmentsBusy={source.attachments.busy}
            attachmentsBlocked={source.attachments.blocked}
            attachments={<DocumentPanel businessNeed scope={{ kind: "requirement", id }}
              onStateChange={source.setAttachments} onContextChanged={() => refresh("source")} />}
            submitLabel="Save requirement"
            busy={source.busy}
            error={source.error ? errorMessage(source.error) : null}
            onCancel={() => source.setEditing(false)}
            onSubmit={source.submit}
          />
        ) : (
          <>
            <section className="grid gap-2" aria-labelledby="source-need">
              <h3 className="text-title text-ink m-0" id="source-need">Business need</h3>
              <p className="font-serif text-document text-ink m-0 whitespace-pre-line">
                {requirement.description || "No business need was written; the attached files carry it."}
              </p>
            </section>
            <RequirementFacts requirement={requirement} />
            <div className="flex flex-wrap items-center gap-3">
              {!requirement.duplicate_of_requirement_id && canGovern && (
                <Button variant="secondary" onClick={() => source.setEditing(true)}>Edit source</Button>
              )}
              <Link className="text-accent text-body inline-flex min-h-6 min-w-6 items-center underline underline-offset-2" to={`/requirements/${id}/revisions`}>
                View revisions
              </Link>
            </div>
          </>
        )}
        {analysis && (
          <section className="grid gap-2 [border-top:1px_solid_var(--line)] pt-4" aria-labelledby="source-analysis">
            <h3 className="text-title text-ink m-0" id="source-analysis">What the analysis holds</h3>
            <dl className="m-0 grid">
              {([
                ["Known facts", analysis.known_facts.length],
                ["Rules and constraints", analysis.business_rules.length + analysis.constraints.length],
                ["Answers from people", analysis.clarifications.length],
              ] as const).map(([label, count]) => (
                <div className="flex items-baseline justify-between gap-4 py-2 [&+&]:[border-top:1px_solid_var(--line)]" key={label}>
                  <dt className="text-body text-ink-soft">{label}</dt>
                  <dd className="text-body text-ink m-0 font-semibold tabular-nums">{count}</dd>
                </div>
              ))}
            </dl>
          </section>
        )}
      </div>
    </section>
  );
}

/**
 * Rendered by the workspace rather than inside the panel: the source drawer can
 * close while this confirmation is still open, and a dialog unmounted by its own
 * trigger disappearing is a dialog a person cannot answer.
 */
export function SourceConfirmation({ source }: { source: SourceEditing }) {
  if (!source.pending || !source.impact) return null;
  return (
    <ConfirmDialog
      title="Save source changes?"
      message={`This edit removes the current analysis and marks ${source.impact.epic_count} Epic, ${source.impact.feature_count} Features, and ${source.impact.story_count} Stories stale. The impact will be checked again before commit.`}
      confirmLabel="Acknowledge and save"
      onCancel={source.dismissImpact}
      onConfirm={source.commitAcknowledged}
    />
  );
}
