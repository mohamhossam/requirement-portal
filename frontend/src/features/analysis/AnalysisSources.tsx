import { createContext, useContext, useId, useState, type ReactNode } from "react";
import { BookOpen, ExternalLink, X } from "lucide-react";
import { Link } from "react-router-dom";

import type { RequirementAnalysis } from "../../api/client";
import { Disclosure } from "../../components/Disclosure";
import { Modal, ModalBody, ModalHeader } from "../../components/Modal";
import { Button } from "../../components/ui/Button";
import { cx } from "../../components/ui/cx";
import { HOVER_GROUND, TRANSITION } from "../../components/ui/recipes";

/**
 * Where a statement came from.
 *
 * This control repeats on every fact, rule, constraint, proposal and question
 * on the Clarify screen — thirty of them on a busy requirement — so it is the
 * single most-repeated element there and it has to be quiet. It reads as a
 * footnote until it is hovered or focused.
 *
 * Restyled onto the shared `Modal` drawer and the token palette. The eight
 * `.analysis-sources-*` rules it used to carry were hardcoded light values
 * (`#506176`, `#edf2f7`, `white`, `#15253626`) that painted over the dark theme
 * `tokens.css` ships, and the drawer duplicated a `Modal` variant that already
 * exists.
 */

type Evidence = RequirementAnalysis["known_facts"][number]["evidence_references"][number];
type Answer = RequirementAnalysis["clarifications"][number];
type Selection = {
  subject: string;
  evidence: Evidence[];
  humanAnswers: Answer[];
  trigger: HTMLButtonElement;
};

const SourcesContext = createContext<((selection: Selection) => void) | null>(null);

function unique<T>(items: T[], key: (item: T) => string): T[] {
  const seen = new Set<string>();
  return items.filter((item) => {
    const identity = key(item);
    if (seen.has(identity)) return false;
    seen.add(identity);
    return true;
  });
}

export function SourceLinks({
  subject,
  evidence = [],
  humanAnswers = [],
}: {
  subject: string;
  evidence?: Evidence[];
  humanAnswers?: Answer[];
}) {
  const open = useContext(SourcesContext);
  const references = unique(evidence, (item) =>
    JSON.stringify([item.document_id, item.version_id, item.checksum_sha256, item.block_id, item.label]),
  );
  const answers = unique(humanAnswers, (item) =>
    JSON.stringify([
      item.question_id,
      item.kind,
      item.subject,
      item.answer,
      item.answered_by?.id,
      item.answered_by?.display_name,
      item.answered_by?.email,
      item.answered_at,
      item.source_suggestion_id,
    ]),
  );
  if (!references.length && !answers.length) return null;

  const counts = [
    references.length
      ? `${references.length} document reference${references.length === 1 ? "" : "s"}`
      : null,
    answers.length ? `${answers.length} human answer${answers.length === 1 ? "" : "s"}` : null,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <button
      aria-haspopup="dialog"
      aria-label={`Where this came from: ${subject}`}
      /* `min-h-6`: the 24px floor of WCAG 2.2 2.5.8, at the primitive rather
         than per screen (design-system.md §6). */
      className={cx(
        "text-meta text-ink-muted inline-flex min-h-6 w-fit cursor-pointer items-center gap-1.5",
        "rounded-sm border border-solid border-transparent bg-transparent px-1.5 py-0.5 text-left",
        "hover:text-ink hover:border-line",
        TRANSITION,
        HOVER_GROUND,
      )}
      onClick={(event) =>
        open?.({ subject, evidence: references, humanAnswers: answers, trigger: event.currentTarget })
      }
      type="button"
    >
      <BookOpen aria-hidden="true" className="shrink-0" size={13} />
      <span>
        Where this came from <span className="text-ink-faint">· {counts}</span>
      </span>
    </button>
  );
}

function SourcesDialog({
  selection,
  documents,
  onClose,
}: {
  selection: Selection;
  documents: RequirementAnalysis["document_references"];
  onClose: () => void;
}) {
  const titleId = useId();
  const groups = new Map<string, Evidence[]>();
  for (const reference of selection.evidence) {
    const key = JSON.stringify([
      reference.document_id,
      reference.version_id,
      reference.checksum_sha256,
    ]);
    groups.set(key, [...(groups.get(key) ?? []), reference]);
  }

  return (
    <Modal
      className="grid content-start gap-4 [overflow-wrap:anywhere]"
      labelledBy={titleId}
      onClose={onClose}
      portal
      restoreFocusTo={selection.trigger}
      variant="drawer"
    >
      <div className="flex items-start justify-between gap-4">
        <ModalHeader
          description="The evidence behind this statement."
          id={titleId}
          title="Where this came from"
        />
        <Button
          aria-label="Close"
          autoFocus
          icon={<X aria-hidden="true" size={18} />}
          onClick={onClose}
          size="icon"
          variant="ghost"
        />
      </div>

      <ModalBody>
        <p className="border-line bg-surface-sunken text-document text-ink m-0 rounded-md border border-solid border-l-[3px] border-l-[var(--line-strong)] p-3 font-serif">
          {selection.subject}
        </p>

        {groups.size > 0 && (
          <section aria-label="Source documents" className="grid gap-3">
            <h3 className="text-title text-ink m-0">In the source documents</h3>
            {[...groups.entries()].map(([key, references]) => {
              const first = references[0];
              if (!first) return null;
              const document = documents.find(
                (item) =>
                  item.document_id === first.document_id &&
                  item.version_id === first.version_id &&
                  item.checksum_sha256 === first.checksum_sha256,
              );
              return (
                <article
                  className="border-line grid gap-2 rounded-md border border-solid p-3"
                  key={key}
                >
                  <h4 className="text-body text-ink m-0 font-semibold">
                    {document?.filename ?? "A source document"}
                  </h4>
                  <ul className="m-0 grid list-none gap-3 p-0">
                    {references.map((reference) => (
                      <li className="grid gap-1" key={JSON.stringify(reference)}>
                        <span className="text-ink-soft text-body">{reference.label}</span>
                        <Link
                          className="text-accent text-body inline-flex w-fit items-center gap-1.5 underline underline-offset-2"
                          rel="noopener noreferrer"
                          target="_blank"
                          to={`/documents/${reference.document_id}#block-${reference.block_id}`}
                        >
                          Open this passage
                          <ExternalLink aria-hidden="true" size={13} />
                          <span className="sr-only"> (opens in a new tab)</span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                  <Disclosure label={<span className="text-meta">Exact reference</span>}>
                    <dl className="text-meta m-0 grid gap-1.5">
                      <dt className="text-ink-muted">Document</dt>
                      <dd className="text-mono text-ink-soft m-0 font-mono">
                        {first.document_id}
                      </dd>
                      <dt className="text-ink-muted">Version</dt>
                      <dd className="text-mono text-ink-soft m-0 font-mono">{first.version_id}</dd>
                      <dt className="text-ink-muted">Checksum</dt>
                      <dd className="text-mono text-ink-soft m-0 font-mono">
                        {first.checksum_sha256}
                      </dd>
                    </dl>
                  </Disclosure>
                </article>
              );
            })}
          </section>
        )}

        {selection.humanAnswers.length > 0 && (
          <section aria-label="Human answers" className="grid gap-3">
            <h3 className="text-title text-ink m-0">From someone's answer</h3>
            {selection.humanAnswers.map((answer, index) => (
              <article
                className="border-line grid gap-2 rounded-md border border-solid p-3"
                key={index}
              >
                <h4 className="text-body text-ink m-0 font-semibold">{answer.subject}</h4>
                <p className="text-document text-ink-soft m-0 font-serif">{answer.answer}</p>
                <p className="text-ink-muted text-meta m-0">
                  {answer.answered_by?.display_name ?? "The answering person is not on record"}
                  {answer.answered_at
                    ? ` · ${new Date(answer.answered_at).toLocaleString()}`
                    : ""}
                  {answer.source_suggestion_id ? " · from a grounded suggestion" : ""}
                </p>
              </article>
            ))}
          </section>
        )}
      </ModalBody>
    </Modal>
  );
}

export function AnalysisSourcesProvider({
  children,
  documents,
}: {
  children: ReactNode;
  documents: RequirementAnalysis["document_references"];
}) {
  const [selection, setSelection] = useState<Selection | null>(null);
  return (
    <SourcesContext.Provider value={setSelection}>
      {children}
      {selection && (
        <SourcesDialog
          documents={documents}
          onClose={() => setSelection(null)}
          selection={selection}
        />
      )}
    </SourcesContext.Provider>
  );
}
