import { UserRound } from "lucide-react";

import type { RequirementAnalysis } from "../../api/client";
import { cx } from "../../components/ui";
import { SourceLinks } from "./AnalysisSources";
import { humanEvidence, when } from "./analysisFormat";

type EvidenceReference = RequirementAnalysis["known_facts"][number]["evidence_references"][number];
export function ColumnHeading({ id, children, count }: { id: string; children: string; count?: string }) {
  return (
    <div className="border-line flex items-baseline justify-between gap-3 border-0 border-b border-solid pb-2">
      <h2 className="text-headline text-ink m-0" id={id}>
        {children}
      </h2>
      {count && <span className="text-ink-muted text-meta tabular-nums">{count}</span>}
    </div>
  );
}

function SettledList({
  analysis,
  title,
  kind,
  items,
}: {
  analysis: RequirementAnalysis;
  title: string;
  kind: string;
  items: { statement: string; evidence_references: EvidenceReference[] }[];
}) {
  return (
    <section aria-label={title} className="grid gap-2">
      <h3 className="text-label text-ink-muted m-0">{title}</h3>
      {items.length ? (
        <ul className="grid list-none gap-3 p-0">
          {items.map((item) => (
            <li className="grid gap-1" key={item.statement}>
              <span className="text-document text-ink-soft font-serif">{item.statement}</span>
              <SourceLinks
                evidence={item.evidence_references}
                humanAnswers={humanEvidence(analysis, kind, item.statement)}
                subject={item.statement}
              />
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-ink-muted text-body m-0">Nothing recorded yet.</p>
      )}
    </section>
  );
}

/**
 * The left column: this requirement as it currently stands.
 *
 * Statements here are single sentences, not paragraphs, which is why a ~300px
 * column is the right measure for them and why the work gets the wider track.
 */
export function SettledColumn({
  analysis,
  className,
  intent,
  pending,
}: {
  analysis: RequirementAnalysis;
  className?: string;
  intent: React.ReactNode;
  /** Answers written but not yet sent. Provisional, and labelled as such. */
  pending: { id: string; subject: string; answer: string }[];
}) {
  const answers = analysis.clarifications;
  const settledCount =
    analysis.known_facts.length + analysis.business_rules.length + analysis.constraints.length;

  return (
    /* A named region, like the working column beside it: two landmarks is the
       fastest way for a screen-reader user to move between what is done and
       what is left (design-system.md §13, bar 15). */
    <section aria-labelledby="settled-heading" className={cx("grid content-start gap-5", className)}>
      <ColumnHeading count={`${settledCount} recorded`} id="settled-heading">
        What is settled
      </ColumnHeading>

      {intent}

      <SettledList
        analysis={analysis}
        items={analysis.known_facts}
        kind="known_fact"
        title="Known facts"
      />
      <SettledList
        analysis={analysis}
        items={analysis.business_rules}
        kind="business_rule"
        title="Business rules"
      />
      <SettledList
        analysis={analysis}
        items={analysis.constraints}
        kind="constraint"
        title="Constraints"
      />

      {/* The one thing on this screen that actually crosses.
       *
       * The direction contract promises "answering moves an item across", and
       * until now nothing did: the settled column was byte-identical before and
       * after answering every question, because an answer is not settled until
       * it has been sent and a round has accepted it. So this does not claim
       * they are settled — it says exactly what they are, on a dashed ground,
       * and the question stays in the open column where it can still be edited.
       * What a person gets is the feedback the thesis promised: this column
       * grows as they work. PRODUCT.md Principle 1 is why it is labelled rather
       * than quietly merged into the facts above it. */}
      {pending.length > 0 && (
        <section aria-label="Answered, waiting to be sent" className="grid gap-2">
          <h3 className="text-label text-ink-muted m-0">
            Answered, waiting to be sent ({pending.length})
          </h3>
          <dl className="m-0 grid gap-3">
            {pending.map((item) => (
              <div
                className="border-line-strong grid gap-1 rounded-sm border border-dashed p-3"
                key={item.id}
              >
                <dt className="text-body text-ink-muted m-0">{item.subject}</dt>
                <dd className="text-document text-ink-soft m-0 font-serif">{item.answer}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}

      {answers.length > 0 && (
        <section aria-label="Answers already given" className="grid gap-2">
          <h3 className="text-label text-ink-muted m-0">
            Answers already given ({answers.length})
          </h3>
          <dl className="m-0 grid gap-3">
            {answers.map((item) => (
              <div
                className="border-line border-0 border-l border-solid pl-3"
                key={item.question_id ?? `${item.kind}-${item.subject}`}
              >
                <dt className="text-body text-ink-muted m-0">{item.subject}</dt>
                <dd className="text-document text-ink-soft m-0 mt-1 font-serif">{item.answer}</dd>
                <p className="text-ink-muted text-meta m-0 mt-1 flex items-center gap-1.5">
                  <UserRound size={12} aria-hidden="true" />
                  {item.answered_by?.display_name ?? "The answering person is not on record"}
                  {item.answered_at ? ` · ${when(item.answered_at)}` : ""}
                  {item.source_suggestion_id ? " · from a grounded suggestion" : ""}
                </p>
              </div>
            ))}
          </dl>
        </section>
      )}
    </section>
  );
}
