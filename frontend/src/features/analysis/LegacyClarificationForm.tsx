import type { ClarificationAnswerInput, ClarificationKind } from "../../api/client";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Badge, Button, Card, Textarea } from "../../components/ui";
import { KIND_LABEL } from "./labels";

export type LegacyEntry = { kind: ClarificationKind; primary: string; secondary?: string | null };
const clarificationCategories: ReadonlyArray<{ kind: ClarificationKind; title: string }> = [
  { kind: "assumption", title: "Assumptions" },
  { kind: "open_question", title: "Open questions" },
  { kind: "ambiguity", title: "Ambiguities" },
  { kind: "potential_dependency", title: "Potential dependencies" },
];

/**
 * The pre-question-ID analyses. They have no stable IDs, so they resolve as one
 * compatible batch and cannot be assigned, classified or drafted. Restyled into
 * the same vocabulary; the submit path is unchanged.
 */
export function LegacyClarificationForm({
  answers,
  busy,
  entries,
  error,
  onClarify,
  setAnswers,
}: {
  answers: Record<string, string>;
  busy: boolean;
  entries: LegacyEntry[];
  error: string | null;
  onClarify: (answers: ClarificationAnswerInput[]) => void;
  setAnswers: React.Dispatch<React.SetStateAction<Record<string, string>>>;
}) {
  return (
    <form
      className="grid gap-4"
      onSubmit={(event) => {
        event.preventDefault();
        onClarify(
          entries.flatMap((entry) => {
            const answer = answers[`${entry.kind}\u0000${entry.primary}`]?.trim();
            return answer ? [{ kind: entry.kind, subject: entry.primary, answer }] : [];
          }),
        );
      }}
    >
      <p className="border-line bg-warning-wash text-ink-soft text-body m-0 rounded-md border border-solid border-l-[3px] border-l-[var(--warning-edge)] p-3">
        This analysis predates individually tracked questions, so these are answered and sent
        together.
      </p>
      {clarificationCategories.map((category) => {
        const group = entries.filter((entry) => entry.kind === category.kind);
        if (!group.length) return null;
        return (
          <section
            aria-labelledby={`legacy-${category.kind}`}
            className="grid gap-3"
            key={category.kind}
          >
            <h3 className="text-title text-ink m-0" id={`legacy-${category.kind}`}>
              {category.title} ({group.length})
            </h3>
            {group.map((entry, index) => {
              const key = `${entry.kind}\u0000${entry.primary}`;
              return (
                <Card padding="compact" className="grid gap-3" key={key}>
                  <Badge tone="neutral">{KIND_LABEL[entry.kind]}</Badge>
                  <h4 className="text-document text-ink m-0 max-w-[68ch] font-serif font-semibold">
                    {entry.primary}
                  </h4>
                  {entry.secondary && (
                    <p className="text-ink-muted text-body m-0 max-w-[68ch]">{entry.secondary}</p>
                  )}
                  <Textarea
                    id={`clarification-${category.kind}-${index}`}
                    label="Your answer"
                    onChange={(event) =>
                      setAnswers((current) => ({ ...current, [key]: event.target.value }))
                    }
                    rows={3}
                    value={answers[key] ?? ""}
                  />
                </Card>
              );
            })}
          </section>
        );
      })}
      {error && <ErrorNotice message={error} />}
      <div>
        <Button disabled={busy} type="submit" variant="primary">
          Send these answers and re-analyse
        </Button>
      </div>
    </form>
  );
}
