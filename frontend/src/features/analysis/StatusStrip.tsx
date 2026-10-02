import { Check, Sparkles } from "lucide-react";

import type { RequirementAnalysis } from "../../api/client";
import { when } from "./analysisFormat";

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
}: {
  analysis: RequirementAnalysis;
  answered: number;
  open: number;
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
                ? `${analysis.confirmed_by?.display_name ?? "The confirming person is not on record"} · ${when(analysis.confirmed_at)}`
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
    </div>
  );
}

/** One statement of settled understanding, with whatever backs it up. */
