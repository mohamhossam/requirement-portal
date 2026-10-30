import { Check, CircleAlert, Download, FileText, Sparkles } from "lucide-react";

import type { RequirementAnalysis, SpecificationFormat } from "../../api/client";
import { Button } from "../../components/ui/Button";
import { whenLabel } from "../revisions/labels";

/** The Business Requirements Document of the confirmed analysis (ADR-0119), offered once confirmed. */
export type SpecificationDownload = {
  /** The backlog version the document is built from. */
  revision: number;
  /** The format being prepared right now, so only its button says so. */
  busy: SpecificationFormat | null;
  error: string | null;
  /** The format of the download that last finished. */
  downloaded: SpecificationFormat | null;
  onDownload: (format: SpecificationFormat) => void;
};

const SPECIFICATION_LABELS: Record<SpecificationFormat, string> = { docx: "Word document", md: "Markdown" };

/**
 * Provenance and progress, on one line.
 *
 * Provenance is **glyph plus label on `--surface-sunken`**, never a wash
 * (§4.5, amended): the accent wash this used to carry measured 1.17:1 against
 * the panel in light and 1.07:1 in dark, so it was never a signal, and spending
 * the accent on a register broke §4.4's "one accent, once" on a screen that
 * needs it for the next action.
 */
export function StatusStrip({
  analysis,
  answered,
  open,
  specification = null,
}: {
  analysis: RequirementAnalysis;
  answered: number;
  open: number;
  specification?: SpecificationDownload | null;
}) {
  const confirmed = analysis.human_confirmed;
  const total = Math.max(answered + open, 1);
  const Glyph = confirmed ? Check : Sparkles;

  return (
    <div className="border-line bg-surface grid gap-3 rounded-md border border-solid p-4">
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <p className="m-0 flex items-start gap-2">
          <span className="bg-surface-sunken text-ink-muted mt-0.5 grid size-6 shrink-0 place-items-center rounded-full">
            <Glyph size={14} aria-hidden="true" />
          </span>
          <span className="grid gap-0.5">
            <span className="text-title text-ink">
              {confirmed ? "Confirmed by a person" : "Drafted by the analysis"}
            </span>
            <span className="text-ink-muted text-meta">
              {confirmed
                ? `${analysis.confirmed_by?.display_name ?? "The confirming person is not on record"} · ${
                    analysis.confirmed_at ? whenLabel(analysis.confirmed_at) : "an unrecorded date"
                  }`
                : `Round ${analysis.round_number ?? "before rounds were numbered"} · nobody has confirmed this yet`}
            </span>
          </span>
        </p>
        <p className="text-ink-muted text-meta m-0 tabular-nums">
          {open === 0 ? (
            <span className="text-success font-semibold">Everything has been answered</span>
          ) : (
            <>
              <span className="text-ink font-semibold">{open} still open</span> · {answered} answered
            </>
          )}
        </p>
      </div>
      {/* A real <progress> carries the value to assistive technology; the bar
          below it is the same number drawn, so the two cannot disagree. */}
      <progress
        aria-label="Questions answered"
        className="sr-only"
        max={total}
        value={answered}
      />
      <span aria-hidden="true" className="bg-surface-sunken block h-1 overflow-hidden rounded-full">
        {/* scaleX, not width: transform and opacity are the two properties
            that animate without asking the browser for another layout. */}
        <span
          className="bg-accent block h-full w-full origin-left rounded-full transition-transform duration-[var(--motion-base)] ease-out motion-reduce:transition-none"
          style={{ transform: `scaleX(${answered / total})` }}
        />
      </span>
      {confirmed && specification && (
        <div
          aria-label="Business Requirements Document"
          className="border-line flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-0 border-t border-solid pt-3"
          role="group"
        >
          <p className="text-ink text-meta m-0 flex items-center gap-2">
            <FileText aria-hidden="true" className="text-ink-muted shrink-0" size={14} />
            <span>Business Requirements Document, from backlog version {specification.revision}</span>
          </p>
          <div className="flex flex-wrap items-center gap-2">
            {/* Kept enabled while the file is prepared, so focus stays put; a second press is ignored. */}
            <Button
              aria-busy={specification.busy === "docx" || undefined}
              icon={<Download aria-hidden="true" size={16} />}
              onClick={() => {
                if (!specification.busy) specification.onDownload("docx");
              }}
              size="sm"
              variant="secondary"
            >
              {specification.busy === "docx" ? "Preparing the Word document…" : "Download Word document"}
            </Button>
            <Button
              aria-busy={specification.busy === "md" || undefined}
              onClick={() => {
                if (!specification.busy) specification.onDownload("md");
              }}
              size="sm"
              variant="text"
            >
              {specification.busy === "md" ? "Preparing the Markdown…" : "Download Markdown"}
            </Button>
          </div>
          <p aria-live="polite" className="text-ink-soft text-meta m-0 basis-full empty:hidden" role="status">
            {!specification.busy && specification.downloaded && !specification.error
              ? `Downloaded version ${specification.revision} as ${SPECIFICATION_LABELS[specification.downloaded]}.`
              : ""}
          </p>
          {specification.error && (
            <p className="text-danger text-meta m-0 flex basis-full items-start gap-1.5 font-semibold" role="alert">
              <CircleAlert aria-hidden="true" className="mt-px shrink-0" size={14} />
              <span>The download did not complete: {specification.error} Try again; the file is prepared fresh each time.</span>
            </p>
          )}
        </div>
      )}
    </div>
  );
}

/** One statement of settled understanding, with whatever backs it up. */
