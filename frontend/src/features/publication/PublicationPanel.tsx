import { CircleAlert, ExternalLink, Send } from "lucide-react";
import { useState } from "react";

import type { PublicationPreview, PublicationReport } from "../../api/client";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Skeleton } from "../../components/Skeleton";
import { Badge, type BadgeTone } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow } from "../../components/ui/Table";

export type PanelError = { message: string; reference?: string | null };

type Props = {
  revision: number;
  preview: PublicationPreview | null;
  previewLoading: boolean;
  /** Publishing is not set up for this portal: say so once, offer nothing. */
  unavailable: string | null;
  previewError: PanelError | null;
  canPublish: boolean;
  publishing: boolean;
  report: PublicationReport | null;
  publishError: PanelError | null;
  onPublish: (approvalFingerprint: string) => void;
};

const OUTCOME: Record<PublicationReport["outcome"], { tone: BadgeTone; label: string; text: string }> = {
  published: { tone: "success", label: "Published", text: "Every item was created." },
  partial: {
    tone: "warning",
    label: "Partly published",
    text: "Some items were created before one was refused. The created items stay in the tracker; nothing under the refused item was sent.",
  },
  failed: { tone: "danger", label: "Not published", text: "The first item was refused, so nothing was created." },
};

const STEP: Record<PublicationReport["steps"][number]["status"], { tone: BadgeTone; label: string }> = {
  published: { tone: "success", label: "Created" },
  failed: { tone: "danger", label: "Refused" },
  not_attempted: { tone: "neutral", label: "Not sent" },
};

/** Preview the approved backlog's work items, and publish them after an explicit confirmation. */
export function PublicationPanel({
  revision,
  preview,
  previewLoading,
  unavailable,
  previewError,
  canPublish,
  publishing,
  report,
  publishError,
  onPublish,
}: Props) {
  const [confirming, setConfirming] = useState(false);

  return (
    <Card aria-labelledby="publication-title" className="grid gap-4" padding="fluid">
      <header className="grid gap-1">
        <h2 className="text-headline text-ink m-0" id="publication-title">
          Publish version {revision} to Azure DevOps
        </h2>
        <p className="text-body text-ink-muted m-0 max-w-[var(--measure-document)]">
          The approved backlog becomes work items, each linked under its parent. Nothing is sent until the owner
          confirms.
        </p>
      </header>

      {unavailable ? (
        <p className="text-body text-ink-soft m-0">{unavailable}</p>
      ) : previewLoading ? (
        <Skeleton label="Loading the publication preview" variant="panel" />
      ) : previewError ? (
        <ErrorNotice message={previewError.message} reference={previewError.reference} />
      ) : preview ? (
        <>
          <dl className="text-body m-0 grid gap-x-6 gap-y-1 sm:grid-cols-[max-content_1fr]">
            <dt className="text-ink-muted">Target</dt>
            <dd className="text-ink m-0">
              {preview.target.system}, project {preview.target.project}
            </dd>
            <dt className="text-ink-muted">Default area</dt>
            <dd className="text-ink m-0">{preview.target.default_location}</dd>
            {preview.target.details.map((detail) => (
              <FactRow key={detail.label} label={detail.label} value={detail.value} />
            ))}
            <dt className="text-ink-muted">Items</dt>
            <dd className="text-ink m-0">
              {preview.counts.epics} Epic, {preview.counts.features} Features, {preview.counts.stories} Stories
            </dd>
          </dl>

          <Table caption={`Work items for version ${revision}`}>
            <TableHead>
              <TableRow>
                <TableHeaderCell>Item</TableHeaderCell>
                <TableHeaderCell>Title</TableHeaderCell>
                <TableHeaderCell>Lands in</TableHeaderCell>
                {report && <TableHeaderCell>Result</TableHeaderCell>}
              </TableRow>
            </TableHead>
            <TableBody columns={report ? 4 : 3}>
              {preview.items.map((item) => {
                const step = report?.steps.find((candidate) => candidate.key === item.key);
                return (
                  <TableRow key={item.key}>
                    <TableCell className="whitespace-nowrap">
                      <span className={item.kind === "story" ? "pl-8" : item.kind === "feature" ? "pl-4" : undefined}>
                        {item.label}
                      </span>
                    </TableCell>
                    <TableCell>{item.title}</TableCell>
                    <TableCell>
                      {item.location}
                      {item.owning_squad_name && (
                        <span className="text-meta text-ink-muted block">Owned by {item.owning_squad_name}</span>
                      )}
                    </TableCell>
                    {report && (
                      <TableCell>
                        {step ? (
                          <span className="grid gap-1">
                            <Badge tone={STEP[step.status].tone}>{STEP[step.status].label}</Badge>
                            {step.url && (
                              <a className="text-meta inline-flex items-center gap-1" href={step.url} rel="noreferrer" target="_blank">
                                Open item {step.external_id}
                                <ExternalLink aria-hidden="true" size={12} />
                                <span className="sr-only">(opens in a new tab)</span>
                              </a>
                            )}
                            {step.error && <span className="text-meta text-danger">{step.error}</span>}
                          </span>
                        ) : null}
                      </TableCell>
                    )}
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>

          {report && (
            <p aria-live="polite" className="text-body m-0 flex flex-wrap items-center gap-2" role="status">
              <Badge tone={OUTCOME[report.outcome].tone}>{OUTCOME[report.outcome].label}</Badge>
              <span className="text-ink-soft">{OUTCOME[report.outcome].text}</span>
            </p>
          )}
          {publishError && <ErrorNotice message={publishError.message} reference={publishError.reference} />}

          {canPublish ? (
            <Button
              className="w-fit"
              icon={<Send aria-hidden="true" size={16} />}
              loading={publishing}
              loadingLabel="Publishing…"
              onClick={() => setConfirming(true)}
              variant="primary"
            >
              Publish to {preview.target.system}
            </Button>
          ) : (
            <p className="text-meta text-ink-muted m-0 flex items-start gap-1.5">
              <CircleAlert aria-hidden="true" className="mt-px shrink-0" size={14} />
              <span>Only the requirement’s owner can publish.</span>
            </p>
          )}
          {confirming && (
            <ConfirmDialog
              confirmLabel="Publish"
              message={`This creates ${preview.items.length} work items in ${preview.target.system} project ${preview.target.project}, exactly as version ${revision} was approved. They cannot be removed from this portal.`}
              onCancel={() => setConfirming(false)}
              onConfirm={() => {
                setConfirming(false);
                onPublish(preview.approval_fingerprint);
              }}
              title={`Publish version ${revision}?`}
            />
          )}
        </>
      ) : null}
    </Card>
  );
}

function FactRow({ label, value }: { label: string; value: string }) {
  return (
    <>
      <dt className="text-ink-muted">{label}</dt>
      <dd className="text-ink m-0">{value}</dd>
    </>
  );
}
