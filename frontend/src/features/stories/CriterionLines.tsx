import type { AcceptanceCriterion } from "../../api/client";

const KEYWORDS = [
  ["given", "Given"],
  ["when", "When"],
  ["then", "Then"],
] as const;

/**
 * One acceptance criterion as three lines: the keyword in the interface face,
 * the words in the document serif (docs/design-system.md §3) — the criterion is
 * requirement prose, the keyword is the method's scaffolding around it.
 */
export function CriterionLines({ criterion }: { criterion: AcceptanceCriterion }) {
  return (
    <>
      {KEYWORDS.map(([key, word]) => (
        <span className="font-document text-document text-ink-soft leading-[1.6]" key={key}>
          <strong className="text-label text-ink-muted inline-block min-w-[3.2rem] font-sans font-semibold">{word}</strong>{" "}
          {criterion[key]}
        </span>
      ))}
    </>
  );
}
