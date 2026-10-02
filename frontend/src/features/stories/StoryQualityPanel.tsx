import { AlertTriangle, Check, Scissors } from "lucide-react";

import type { StoryQuality } from "../../api/client";
import { ProvenanceDetails } from "../../components/ProvenanceDetails";
import { Disclosure } from "../../components/Disclosure";
import { Card } from "../../components/ui";

const labels = {
  independent: "Independent",
  negotiable: "Negotiable",
  valuable: "Valuable",
  estimable: "Estimable",
  small: "Small",
  testable: "Testable",
};

const HEADLINE: Record<StoryQuality["status"], string> = {
  passes: "Passes all checks",
  split_recommended: "Split recommended",
  needs_attention: "Needs attention",
};

/** The five SPIDR splitting patterns, as names rather than API values. */
const SPIDR: Record<string, string> = {
  spike: "Spike",
  paths: "Paths",
  interfaces: "Interfaces",
  data: "Data",
  rules: "Rules",
};

/**
 * Who reached the finding. `deterministic` and `semantic` are the API's words,
 * and they were reaching the screen unchanged — a business owner reading
 * "semantic" under a quality concern learns nothing about how much to trust it.
 * PRODUCT.md Principle 2 makes the distinction worth stating plainly: one is a
 * rule the product applied, the other is the model's judgement.
 */
const SOURCE: Record<string, string> = {
  deterministic: "Rule-based check",
  semantic: "AI judgement",
};

/**
 * INVEST quality for one Story.
 *
 * This panel was the last live corner of a retired visual generation: a 2px
 * `#201e1d` warm near-black frame on a hard `#fff` ground, with its own amber
 * and green washes and 0.62rem type. docs/ux-plan.md §3.9 lists that near-black
 * among the three dead generations to delete, and the white ground put the whole
 * panel at 1.02:1 in the dark theme. It is a `Card` in the system's tones now,
 * and nothing here names a colour.
 */
export function StoryQualityPanel({
  quality,
  focused = false,
  title,
}: {
  quality: StoryQuality;
  focused?: boolean;
  /**
   * Which Story this is, where the panel is not already inside the Story's own
   * card. Review & approve lists several of these; without a name each one was
   * "Is this Story ready to build?" in a region called "INVEST quality review",
   * four times over, and a failing one could not be told from the rest.
   */
  title?: string;
}) {
  const findings = focused ? quality.findings.filter((finding) => !finding.passed) : quality.findings;
  const passing = quality.findings.filter((finding) => finding.passed);

  return (
    <Card
      as="section"
      aria-label={title ? `Readiness checks: ${title}` : "INVEST quality review"}
      tone={quality.status === "passes" ? "success" : "warning"}
      className={title ? "quality-panel" : "quality-panel mt-5"}
    >
      {/* A real heading rather than a label over a `<strong>`: the craft floor
          bans the kicker, and the loudest line on the panel was sitting outside
          the document outline between an `h2` and an `h4`. */}
      <header className="border-line mb-4 border-0 border-b border-solid pb-3">
        {title
          ? <h4 className="text-title text-ink m-0">Is it ready to build?</h4>
          : <h3 className="text-title text-ink m-0">Is this Story ready to build?</h3>}
        <p className="text-ink-muted text-meta m-0 mt-0.5">
          Six checks on whether it can be estimated, tested and finished in one sprint.
        </p>
        <p className="text-body text-ink-soft m-0 mt-2 tabular-nums">
          {HEADLINE[quality.status]}
          {quality.failure_count > 0 &&
            ` — ${quality.failure_count} of ${quality.findings.length} checks failed`}
        </p>
      </header>

      {/* Nothing failed and only failures are shown: no list, rather than an
          empty band between the header and the disclosure. */}
      {findings.length > 0 && <ul className="m-0 grid list-none gap-3 p-0 sm:grid-cols-2">
        {findings.map((finding) => (
          <li key={finding.criterion} className="grid grid-cols-[auto_1fr] gap-2">
            {finding.passed ? (
              <Check aria-hidden="true" className="text-success mt-0.5 shrink-0" size={16} />
            ) : (
              <AlertTriangle aria-hidden="true" className="text-warning mt-0.5 shrink-0" size={16} />
            )}
            <div className="grid min-w-0 gap-0.5">
              <strong className="text-body text-ink">
                {labels[finding.criterion]}
                {/* Never colour alone: the glyph and this word both say it. */}
                <span className="sr-only">{finding.passed ? " — passed" : " — failed"}</span>
              </strong>
              <p className="font-document text-document text-ink-soft m-0 leading-[1.6]">{finding.message}</p>
              <small className="text-meta text-ink-muted">{SOURCE[finding.source] ?? finding.source}</small>
            </div>
          </li>
        ))}
      </ul>}

      {focused && (
        <Disclosure label={`Successful checks (${passing.length})`}>
          <ul className="m-0 grid list-none gap-3 p-0 sm:grid-cols-2">
            {passing.map((finding) => (
              <li key={finding.criterion} className="grid grid-cols-[auto_1fr] gap-2">
                <Check aria-hidden="true" className="text-success mt-0.5 shrink-0" size={16} />
                <div className="grid min-w-0 gap-0.5">
                  <strong className="text-body text-ink">{labels[finding.criterion]}</strong>
                  <p className="font-document text-document text-ink-soft m-0 leading-[1.6]">{finding.message}</p>
                </div>
              </li>
            ))}
          </ul>
        </Disclosure>
      )}

      {quality.recommendations.length > 0 && (
        <div className="border-line mt-4 border-0 border-t border-solid pt-4">
          <h4 className="text-title text-ink m-0 mb-1 flex items-center gap-2">
            <Scissors size={16} aria-hidden="true" className="text-ink-muted shrink-0" />
            Ways to split it
          </h4>
          <p className="text-ink-muted text-meta m-0 mb-2">
            Named splitting patterns, from the SPIDR method.
          </p>
          <ul className="m-0 grid list-none gap-2 p-0">
            {quality.recommendations.map((item) => (
              <li key={item.pattern} className="grid gap-0.5">
                <strong className="text-body text-ink">{SPIDR[item.pattern] ?? item.pattern}</strong>
                <span className="font-document text-document text-ink-soft leading-[1.6]">{item.reason}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <ProvenanceDetails label="How this quality review was generated" provenance={quality.provenance} />
    </Card>
  );
}
