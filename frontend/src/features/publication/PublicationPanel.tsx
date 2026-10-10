import { CircleAlert, ExternalLink, RotateCcw, Send } from "lucide-react";
import { useState } from "react";

import type { PublicationPreview, PublicationReport, PublicationStatus } from "../../api/client";
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
  /** The publication record: who published what, and whether the last attempt finished. */
  status?: PublicationStatus | null;
  retrying?: boolean;
  onRetry?: () => void;
};

type Item = PublicationPreview["items"][number];

const OUTCOME: Record<PublicationReport["outcome"], { tone: BadgeTone; label: string; text: string }> = {
  published: { tone: "success", label: "Published", text: "Every item is in the tracker and matches this version." },
  partial: {
    tone: "warning",
    label: "Partly published",
    text: "Some items were sent before one was refused. They stay in the tracker; Retry continues from the refused item.",
  },
  failed: { tone: "danger", label: "Not published", text: "The first item was refused, so nothing was sent." },
  interrupted: {
    tone: "warning",
    label: "Interrupted",
    text: "The attempt stopped before it finished. Retry finds what it sent and continues.",
  },
};

const STEP: Record<PublicationReport["steps"][number]["status"], { tone: BadgeTone; label: string }> = {
  created: { tone: "success", label: "Created" },
  updated: { tone: "success", label: "Updated" },
  unchanged: { tone: "neutral", label: "Unchanged" },
  recovered: { tone: "success", label: "Recovered" },
  failed: { tone: "danger", label: "Refused" },
  not_attempted: { tone: "neutral", label: "Not sent" },
};

const ACTION: Record<Item["action"], { tone: BadgeTone; label: string }> = {
  create: { tone: "accent", label: "New" },
  update: { tone: "warning", label: "Changed" },
  unchanged: { tone: "neutral", label: "Unchanged" },
};

const STATUS: Record<PublicationPreview["status"], { tone: BadgeTone; label: string }> = {
  not_published: { tone: "neutral", label: "Not published" },
  in_progress: { tone: "accent", label: "Publishing now" },
  published: { tone: "success", label: "Published" },
  incomplete: { tone: "warning", label: "Incomplete" },
  outdated: { tone: "warning", label: "Outdated" },
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
  status = null,
  retrying = false,
  onRetry,
}: Props) {
  const [confirming, setConfirming] = useState(false);
  const lastAttempt = status?.attempts[0] ?? null;
  // A retry continues the last attempt, so it is offered only for this version's own attempt.
  const canRetry = canPublish && onRetry && preview?.status === "incomplete" && lastAttempt?.revision === revision;
  const creates = preview?.items.filter((item) => item.action === "create").length ?? 0;
  const updates = preview?.items.filter((item) => item.action === "update").length ?? 0;
  const upToDate = preview !== null && preview.status === "published" && creates + updates === 0;

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
            <dt className="text-ink-muted">Status</dt>
            <dd className="text-ink m-0 flex flex-wrap items-center gap-2">
              <Badge tone={STATUS[preview.status].tone}>{STATUS[preview.status].label}</Badge>
              <span className="text-ink-soft">{statusText(preview, lastAttempt)}</span>
            </dd>
          </dl>

          <Table caption={`Work items for version ${revision}`}>
            <TableHead>
              <TableRow>
                <TableHeaderCell>Item</TableHeaderCell>
                <TableHeaderCell>Title</TableHeaderCell>
                <TableHeaderCell>Lands in</TableHeaderCell>
                <TableHeaderCell>{report ? "Result" : "On publish"}</TableHeaderCell>
              </TableRow>
            </TableHead>
            <TableBody columns={4}>
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
                    {report ? (
                      <TableCell>
                        {step ? (
                          <span className="grid gap-1">
                            <Badge tone={STEP[step.status].tone}>{STEP[step.status].label}</Badge>
                            {step.url && <ItemLink externalId={step.external_id} url={step.url} />}
                            {step.error && <span className="text-meta text-danger">{step.error}</span>}
                          </span>
                        ) : null}
                      </TableCell>
                    ) : (
                      <TableCell>
                        <span className="grid gap-1">
                          <Badge tone={ACTION[item.action].tone}>{ACTION[item.action].label}</Badge>
                          {item.url && <ItemLink externalId={item.external_id} url={item.url} />}
                        </span>
                      </TableCell>
                    )}
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>

          {preview.removed.length > 0 && (
            <section aria-labelledby="publication-removed" className="grid gap-1">
              <h3 className="text-body text-ink m-0 font-semibold" id="publication-removed">
                No longer in version {revision}
              </h3>
              <p className="text-meta text-ink-muted m-0">
                These items were published from an earlier version. Publishing leaves them in {preview.target.system};
                close them there if the work is dropped.
              </p>
              <ul className="m-0 grid gap-1 pl-5">
                {preview.removed.map((item) => (
                  <li key={item.local_key}>
                    <ItemLink externalId={item.external_id} url={item.url} /> <span className="text-meta text-ink-muted">({item.kind}, version {item.revision})</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {report && (
            <p aria-live="polite" className="text-body m-0 flex flex-wrap items-center gap-2" role="status">
              <Badge tone={OUTCOME[report.outcome].tone}>{OUTCOME[report.outcome].label}</Badge>
              <span className="text-ink-soft">{OUTCOME[report.outcome].text}</span>
            </p>
          )}
          {publishError && <ErrorNotice message={publishError.message} reference={publishError.reference} />}

          {!canPublish ? (
            <p className="text-meta text-ink-muted m-0 flex items-start gap-1.5">
              <CircleAlert aria-hidden="true" className="mt-px shrink-0" size={14} />
              <span>Only the requirement’s owner can publish.</span>
            </p>
          ) : upToDate ? (
            <p className="text-meta text-ink-muted m-0">
              {preview.target.system} already matches version {revision}; there is nothing to send.
            </p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {canRetry && (
                <Button
                  icon={<RotateCcw aria-hidden="true" size={16} />}
                  loading={retrying}
                  loadingLabel="Retrying…"
                  disabled={publishing}
                  onClick={onRetry}
                  variant="primary"
                >
                  Retry
                </Button>
              )}
              <Button
                icon={<Send aria-hidden="true" size={16} />}
                loading={publishing}
                loadingLabel="Publishing…"
                disabled={retrying || preview.status === "in_progress"}
                onClick={() => setConfirming(true)}
                variant={canRetry ? "secondary" : "primary"}
              >
                {preview.status === "not_published" ? `Publish to ${preview.target.system}` : "Publish changes"}
              </Button>
            </div>
          )}
          {confirming && (
            <ConfirmDialog
              confirmLabel="Publish"
              message={confirmText(preview, revision, creates, updates)}
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

function ItemLink({ externalId, url }: { externalId: string | null; url: string }) {
  return (
    <a className="text-meta inline-flex items-center gap-1" href={url} rel="noreferrer" target="_blank">
      Open item {externalId}
      <ExternalLink aria-hidden="true" size={12} />
      <span className="sr-only">(opens in a new tab)</span>
    </a>
  );
}

function statusText(preview: PublicationPreview, lastAttempt: PublicationStatus["attempts"][number] | null): string {
  const by = lastAttempt ? ` by ${lastAttempt.actor_name}` : "";
  switch (preview.status) {
    case "not_published":
      return "Nothing from this requirement is in the tracker yet.";
    case "in_progress":
      return `An attempt${by} is sending items now.`;
    case "published":
      return `Version ${preview.published_revision ?? preview.revision} was published${by}.`;
    case "incomplete":
      return `The last attempt${by} did not send every item.`;
    case "outdated":
      return `Version ${preview.published_revision ?? "?"} is in the tracker; this version is not yet.`;
  }
}

function confirmText(preview: PublicationPreview, revision: number, creates: number, updates: number): string {
  const where = `${preview.target.system} project ${preview.target.project}`;
  if (preview.status === "not_published") {
    return `This creates ${preview.items.length} work items in ${where}, exactly as version ${revision} was approved. They cannot be removed from this portal.`;
  }
  return `This creates ${creates} and updates ${updates} work items in ${where} to match version ${revision}. Unchanged items are not sent; an update replaces the title, description and acceptance criteria.`;
}

function FactRow({ label, value }: { label: string; value: string }) {
  return (
    <>
      <dt className="text-ink-muted">{label}</dt>
      <dd className="text-ink m-0">{value}</dd>
    </>
  );
}
