import { CircleCheck, Clock, TriangleAlert } from "lucide-react";

import type { Requirement } from "../../api/client";
import { Button, ButtonLink, Card } from "../../components/ui";
import { DocumentPanel } from "../../features/documents/DocumentPanel";
import { missingLabel } from "../../features/documents/labels";
import type { WorkspaceChange } from "../workspaceInvalidation";
import { RequirementFacts } from "./RequirementFacts";
import type { SourceEditing } from "./useSourceEditing";

/**
 * Is this requirement ready to analyse, and if not, what is missing.
 *
 * The baseline critique for Phase 5 found the step contradicting itself: the
 * API's eligibility said "Ready for analysis" in an indigo box while a file that
 * could not be read held "Continue to analysis" shut — and the shut link still
 * navigated on Enter. One verdict now, from both signals, and a gated button
 * that says why. The source itself is on the Source step too, not only in the
 * drawer.
 */
export function CaptureView({
  id,
  requirement,
  canManageContent,
  canGovern,
  source,
  refresh,
}: {
  id: string;
  requirement: Requirement;
  canManageContent: boolean;
  canGovern: boolean;
  source: SourceEditing;
  refresh: (change: WorkspaceChange) => Promise<unknown>;
}) {
  const { eligible, missing_fields: missing } = requirement.analysis_eligibility;
  const checking = source.attachments.busy;
  const fileProblem = source.attachments.blocked;
  const ready = eligible && !checking && !fileProblem;

  const verdict = ready
    ? {
        tone: "success" as const,
        icon: <CircleCheck className="text-success mt-0.5 shrink-0" size={18} aria-hidden="true" />,
        title: "Ready for analysis",
        text: "The business need and every file ticked Include in analysis will be analysed.",
        gate: undefined,
      }
    : checking && eligible
      ? {
          tone: "default" as const,
          icon: <Clock className="text-ink-muted mt-0.5 shrink-0" size={18} aria-hidden="true" />,
          title: "Checking the attached files",
          text: "Analysis can start once every file has been read.",
          gate: "Available once the files are read.",
        }
      : {
          tone: "warning" as const,
          icon: <TriangleAlert className="text-warning mt-0.5 shrink-0" size={18} aria-hidden="true" />,
          title: "Not ready for analysis",
          text: !eligible
            ? `Still needed: ${missingLabel(missing)}.`
            : "A file below could not be read. Retry it, or leave it out of analysis.",
          gate: !eligible ? "Available once the missing items are added." : "Available once that file is settled.",
        };

  return (
    <div className="grid min-w-0 gap-8">
      <Card padding="compact" as="section" tone={verdict.tone} aria-labelledby="capture-verdict" className="grid gap-3">
        <div className="grid grid-cols-[auto_minmax(0,1fr)] items-start gap-x-2 gap-y-3">
          {verdict.icon}
          <div className="grid gap-1" aria-live="polite">
            <h2 className="text-title text-ink m-0" id="capture-verdict">{verdict.title}</h2>
            <p className="text-body text-ink-soft m-0 max-w-[var(--measure-interface)]">{verdict.text}</p>
          </div>
          <div className="col-start-2">
            {ready ? (
              <ButtonLink className="w-fit" variant="primary" to={`/requirements/${id}/clarify`}>
                Continue to analysis
              </ButtonLink>
            ) : (
              <Button blockedReason={verdict.gate} className="w-fit">Continue to analysis</Button>
            )}
          </div>
        </div>
      </Card>

      <section className="grid gap-4" aria-labelledby="capture-need">
        <header className="flex flex-wrap items-start justify-between gap-3">
          <h2 className="text-headline text-ink m-0" id="capture-need">Business need</h2>
          {!requirement.duplicate_of_requirement_id && canGovern && (
            <Button variant="secondary" onClick={() => source.setEditing(true)}>Edit source</Button>
          )}
        </header>
        {requirement.description.trim() ? (
          <p className="font-serif text-document-lead text-ink m-0 max-w-[var(--measure-document)] whitespace-pre-line">
            {requirement.description}
          </p>
        ) : (
          <p className="text-body text-ink-muted m-0">No business need was written; the attached files carry it.</p>
        )}
        <RequirementFacts requirement={requirement} />
      </section>

      {/* The drawer's form carries its own attachment list while it is open. */}
      {!source.editing && (
        <DocumentPanel businessNeed headingLevel="h2" scope={{ kind: "requirement", id }}
          readOnly={!canManageContent} onStateChange={source.setAttachments}
          onContextChanged={() => refresh("source")} />
      )}
    </div>
  );
}
