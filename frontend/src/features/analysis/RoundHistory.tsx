import type { AnalysisRound } from "../../api/client";
import { Disclosure } from "../../components/Disclosure";
import { when } from "./analysisFormat";
import {
  changeActionLabel,
  INTENT_KIND_LABEL,
  questionStatusLabel,
  SEVERITY_LABEL,
} from "./labels";

/**
 * Every immutable round, for the audit question "what did this look like before
 * we answered anything?". A disclosure at the foot of the page: it is a record,
 * not work, and it is the one thing here nobody opens on a normal day.
 */
export function RoundHistory({ rounds }: { rounds: AnalysisRound[] }) {
  return (
    // Anchored: the "since the last round" summary above links here.
    <div id="round-history" className="scroll-mt-[calc(var(--header-height)+var(--space-4))]">
    <Disclosure
      className="border-line bg-surface rounded-md border border-solid p-4"
      label={`Every earlier round (${rounds.length})`}
    >
      {rounds.length ? (
        <ol className="m-0 grid list-none gap-3 p-0">
          {rounds.map((round) => {
            const item = round.analysis;
            const questionsById = new Map(round.questions.map((q) => [q.id, q]));
            const content = [
              ...item.known_facts.map((value) => `Known fact: ${value.statement}`),
              ...item.business_rules.map((value) => `Business rule: ${value.statement}`),
              ...item.constraints.map((value) => `Constraint: ${value.statement}`),
              ...item.business_intent.proposals.map(
                (value) => `Proposed ${INTENT_KIND_LABEL[value.kind].toLowerCase()}: ${value.statement}`,
              ),
            ];
            return (
              <li key={item.analysis_id ?? String(item.round_number)}>
                <Disclosure
                  label={
                    <span className="text-body">
                      <strong>
                        Round {item.round_number ?? "before rounds were numbered"}
                      </strong>{" "}
                      <span className="text-ink-muted">
                        · requirement version {item.source_requirement_version ?? "unknown"}
                      </span>
                    </span>
                  }
                >
                  <div className="text-body text-ink-soft grid gap-3 pt-1">
                    <p className="text-ink-muted text-meta m-0">
                      {item.provenance
                        ? `${item.provenance.model} · ${item.provenance.prompt_version} · ${when(item.provenance.generated_at)}`
                        : "How this round was generated was not recorded."}
                    </p>

                    <section className="grid gap-1">
                      <h3 className="text-label text-ink-muted m-0">What it found</h3>
                      {content.length ? (
                        <ul className="m-0 grid gap-1 pl-5">
                          {content.map((value) => (
                            <li key={value}>{value}</li>
                          ))}
                        </ul>
                      ) : (
                        <p className="text-ink-muted m-0">Nothing was extracted.</p>
                      )}
                    </section>

                    <section className="grid gap-1">
                      <h3 className="text-label text-ink-muted m-0">Source documents</h3>
                      {item.document_references.length ? (
                        <ul className="m-0 grid gap-1 pl-5">
                          {item.document_references.map((document) => (
                            <li key={document.version_id}>
                              {document.filename}{" "}
                              <span className="text-mono text-ink-muted font-mono">
                                {document.checksum_sha256.slice(0, 12)}
                              </span>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="text-ink-muted m-0">None were included.</p>
                      )}
                    </section>

                    <section className="grid gap-1">
                      <h3 className="text-label text-ink-muted m-0">Questions it asked</h3>
                      {round.questions.length ? (
                        <ul className="m-0 grid gap-1 pl-5">
                          {round.questions.map((question) => (
                            <li key={question.id}>
                              <strong>{question.subject}</strong>{" "}
                              <span className="text-ink-muted">
                                · {SEVERITY_LABEL[question.severity]} ·{" "}
                                {question.is_blocker ? "blocked confirmation" : "did not block"} ·{" "}
                                {questionStatusLabel(question.status)}
                                {question.assignee
                                  ? ` · ${question.assignee.display_name}`
                                  : ""}
                              </span>
                              {question.answer ? (
                                <>
                                  {" "}
                                  — answered by{" "}
                                  {question.answered_by?.display_name ?? "someone not on record"}:{" "}
                                  {question.answer}
                                </>
                              ) : question.draft_answer ? (
                                <>
                                  {" "}
                                  — draft by{" "}
                                  {question.draft_updated_by?.display_name ??
                                    "someone not on record"}
                                  : {question.draft_answer}
                                </>
                              ) : null}
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="text-ink-muted m-0">None.</p>
                      )}
                    </section>

                    <section className="grid gap-1">
                      <h3 className="text-label text-ink-muted m-0">
                        What changed from the round before
                      </h3>
                      {item.question_changes.length ? (
                        <ul className="m-0 grid gap-2 pl-5">
                          {item.question_changes.map((change) => {
                            const previous = questionsById.get(change.question_id);
                            const replacement = change.replacement_question_id
                              ? questionsById.get(change.replacement_question_id)
                              : undefined;
                            return (
                              <li key={`${change.action}-${change.question_id}`}>
                                <strong>{changeActionLabel(change.action)}</strong>:{" "}
                                {previous?.subject ?? change.question_id}
                                {replacement && (
                                  <>
                                    {" → "}
                                    <strong>{replacement.subject}</strong>
                                  </>
                                )}
                                <span className="text-ink-muted block">{change.rationale}</span>
                                {previous?.draft_answer && (
                                  <span className="text-ink-muted block">
                                    Draft kept: {previous.draft_answer}
                                  </span>
                                )}
                              </li>
                            );
                          })}
                        </ul>
                      ) : (
                        <p className="text-ink-muted m-0">Nothing was recorded.</p>
                      )}
                    </section>

                    {item.clarifications.length > 0 && (
                      <section className="grid gap-1">
                        <h3 className="text-label text-ink-muted m-0">Answers given</h3>
                        <ul className="m-0 grid gap-1 pl-5">
                          {item.clarifications.map((entry) => (
                            <li key={entry.question_id ?? `${entry.kind}-${entry.subject}`}>
                              <strong>{entry.subject}</strong>: {entry.answer}{" "}
                              <span className="text-ink-muted">
                                · {entry.answered_by?.display_name ?? "someone not on record"}
                              </span>
                            </li>
                          ))}
                        </ul>
                      </section>
                    )}
                  </div>
                </Disclosure>
              </li>
            );
          })}
        </ol>
      ) : (
        <p className="text-ink-muted text-body m-0">
          No earlier rounds were kept for this analysis.
        </p>
      )}
    </Disclosure>
    </div>
  );
}
