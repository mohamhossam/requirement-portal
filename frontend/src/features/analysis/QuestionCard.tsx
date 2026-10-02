import { Check, ChevronRight } from "lucide-react";

import type {
  Actor,
  AnswerSuggestionSet,
  ClarificationQuestion,
  ClarificationSeverity,
  RequirementAnalysis,
} from "../../api/client";
import { Badge, Button, Checkbox, cx, Select, Textarea } from "../../components/ui";
import { HOVER_GROUND, TRANSITION } from "../../components/ui/recipes";
import type { AnalysisPanelProps } from "./AnalysisPanel";
import { SourceLinks } from "./AnalysisSources";
import { humanEvidence, when } from "./analysisFormat";
import {
  evidenceFieldLabel,
  KIND_LABEL,
  questionStatusLabel,
  SEVERITY_LABEL,
  SUGGESTION_SOURCE_LABEL,
} from "./labels";

export function QuestionGroup({
  analysis,
  answers,
  answerSources,
  busy,
  id,
  onAssign,
  onClassify,
  onSaveDraft,
  onSuggestAnswers,
  questions,
  setAnswerSources,
  setAnswers,
  suggestions,
  suggestionsBusy,
  team,
  title,
  tone,
}: {
  analysis: RequirementAnalysis;
  answers: Record<string, string>;
  answerSources: Record<string, string>;
  busy: boolean;
  id: string;
  onAssign?: AnalysisPanelProps["onAssign"];
  onClassify?: AnalysisPanelProps["onClassify"];
  onSaveDraft?: AnalysisPanelProps["onSaveDraft"];
  onSuggestAnswers?: AnalysisPanelProps["onSuggestAnswers"];
  questions: ClarificationQuestion[];
  setAnswerSources: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  setAnswers: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  suggestions: Record<string, AnswerSuggestionSet | null>;
  suggestionsBusy: boolean;
  team: Actor[];
  title: string;
  tone: "warning" | "default";
}) {
  return (
    <section aria-labelledby={`questions-${id}`} className="grid gap-3">
      <div className="flex items-center gap-2">
        <h3 className="text-title text-ink m-0" id={`questions-${id}`}>
          {title}
        </h3>
        <span className="text-ink-muted text-meta tabular-nums">({questions.length})</span>
      </div>
      {questions.map((question) => (
        <QuestionCard
          analysis={analysis}
          answer={answers[question.id] ?? question.draft_answer ?? ""}
          busy={busy}
          key={question.id}
          onAnswer={(value) => setAnswers((current) => ({ ...current, [question.id]: value }))}
          onAssign={onAssign}
          onClassify={onClassify}
          onPickSuggestion={(suggestionId, value) => {
            setAnswers((current) => ({ ...current, [question.id]: value }));
            setAnswerSources((current) => ({ ...current, [question.id]: suggestionId }));
          }}
          onSaveDraft={onSaveDraft}
          onSuggestAnswers={onSuggestAnswers}
          pickedSuggestion={answerSources[question.id]}
          question={question}
          suggestionSet={suggestions[question.id]}
          suggestionsBusy={suggestionsBusy}
          team={team}
          tone={tone}
        />
      ))}
    </section>
  );
}

function QuestionCard({
  analysis,
  answer,
  busy,
  onAnswer,
  onAssign,
  onClassify,
  onPickSuggestion,
  onSaveDraft,
  onSuggestAnswers,
  pickedSuggestion,
  question,
  suggestionSet,
  suggestionsBusy,
  team,
  tone,
}: {
  analysis: RequirementAnalysis;
  answer: string;
  busy: boolean;
  onAnswer: (value: string) => void;
  onAssign?: AnalysisPanelProps["onAssign"];
  onClassify?: AnalysisPanelProps["onClassify"];
  onPickSuggestion: (suggestionId: string, answer: string) => void;
  onSaveDraft?: AnalysisPanelProps["onSaveDraft"];
  onSuggestAnswers?: AnalysisPanelProps["onSuggestAnswers"];
  pickedSuggestion?: string;
  question: ClarificationQuestion;
  suggestionSet?: AnswerSuggestionSet | null;
  suggestionsBusy: boolean;
  team: Actor[];
  tone: "warning" | "default";
}) {
  const loadingSuggestions = !suggestionSet && suggestionsBusy;
  const ready = answer.trim().length > 0;

  /* The evidence a question carries is still held on the legacy per-kind
     collections, matched by subject. Unchanged from the screen this replaces. */
  const evidence = [
    ...analysis.assumptions
      .filter((item) => question.kind === "assumption" && item.statement === question.subject)
      .flatMap((item) => item.evidence_references),
    ...analysis.open_questions
      .filter((item) => question.kind === "open_question" && item.question === question.subject)
      .flatMap((item) => item.evidence_references),
    ...analysis.ambiguities
      .filter((item) => question.kind === "ambiguity" && item.statement === question.subject)
      .flatMap((item) => item.evidence_references),
    ...analysis.potential_dependencies
      .filter(
        (item) => question.kind === "potential_dependency" && item.statement === question.subject,
      )
      .flatMap((item) => item.evidence_references),
  ];

  return (
    /**
     * A row that opens, not a card that is always open.
     *
     * Every question used to render its whole working apparatus at once —
     * evidence, three suggestions, an answer field, a classification
     * disclosure — so one question cost 674px of placeholder content and 1,801px
     * of real content, and the page ran to 4,355px for four of them. You could
     * see one question at a time. The confirmed working session is batch triage:
     * scan everything open, answer the easy ones fast, come back to the hard
     * ones. None of those three verbs survives a list you cannot see.
     *
     * Collapsed, the row carries exactly what triage compares — kind, severity,
     * who owns it, and whether it is answered — so twelve fit a viewport. The
     * material you need to *answer* it lives in the expansion, where it can be
     * as tall as it likes.
     *
     * Rows open independently, and deliberately so.
     *
     * This was a native exclusive accordion (`name="clarify-question"`), which
     * cost more than it bought. Measured: opening any row after the first threw
     * the row you had just clicked 656–689px above the top of the viewport,
     * because the sibling collapsing above it removed its own height from the
     * flow and nothing compensated. You clicked a question and landed in the
     * middle of a form with the question off-screen — eleven times on a twelve
     * question requirement. It also made comparing two questions impossible,
     * which is half of what triage is.
     *
     * What exclusivity was protecting was page height, and collapsing already
     * solved that: rows default closed, so the list is short until a person
     * decides otherwise. Opening two is now their call, not a defect.
     *
     * Still a real `<details>`, so the keyboard, Find-in-page and the
     * accessibility tree all work with no state and no click handler.
     */
    <details
      className={cx(
        /* `--line-strong`, not `--line`. The row is the primary target on this
           screen and `--line` measures 1.38:1 against the surface in light and
           1.40:1 in dark — under the 3:1 that design-system.md §13 bar 2 sets
           for a non-text boundary. `--line-strong` measures 3.71:1, and the
           suggestion buttons inside the row were already using it. */
        "group border-line-strong bg-surface rounded-md border border-solid",
        TRANSITION,
        "focus-within:border-accent",
        tone === "warning" && "border-l-[3px] border-l-[var(--warning-edge)]",
      )}
    >
      {/* `min-h-11`, not a bare padding: the row is the primary target on this
          screen and it stays a comfortable one even when the subject is short. */}
      <summary
        className={cx(
          "grid min-h-11 cursor-pointer list-none grid-cols-[auto_minmax(0,1fr)_auto] items-center",
          "gap-x-3 rounded-md px-3 py-2.5",
          "[&::-webkit-details-marker]:hidden",
          HOVER_GROUND,
          TRANSITION,
        )}
      >
        <ChevronRight
          aria-hidden="true"
          className="text-ink-muted shrink-0 transition-transform duration-[var(--motion-fast)] ease-out group-open:rotate-90 motion-reduce:transition-none"
          size={15}
        />
        <span className="grid min-w-0 gap-0.5">
          {/* The question leads, and it gets two lines rather than one.
              One line is about 55 characters in this column, and deciding
              whether a question is the easy one or the hard one is the whole
              of triage — a clamp that hides the deciding clause costs more
              than the ~20px per row it saves. Long questions still cannot
              push a row past two lines. */}
          <span className="text-document text-ink line-clamp-2 font-serif font-semibold">
            {question.subject}
          </span>
          {/* Slots, not one concatenated string.
           *
           * As a single `truncate`d line this measured 337px against a 337px
           * box — it fitted the fake provider's content by zero pixels and
           * truncated the moment a question was assigned to a named person.
           * Ellipsis cuts the end, so the first things lost were the assignee
           * and "Revised last round", which is the one signal telling a
           * reviewer the question changed under them (PRODUCT.md Principle 4).
           *
           * Severity now sits in a fixed column, so it is at the same x on
           * every row and a person can run their eye down it. Only the
           * assignee — the one genuinely unbounded value — can truncate. */}
          <span className="text-meta text-ink-muted grid grid-cols-[auto_auto_minmax(0,1fr)] items-baseline gap-x-2">
            <span className="truncate">{KIND_LABEL[question.kind]}</span>
            {/* All three severities read as words. Only Critical also spends a
                colour, because a badge on every row discriminates nothing. */}
            <span
              className={cx(
                "border-line border-0 border-l border-solid pl-2",
                question.severity === "high" && "text-danger font-semibold",
              )}
            >
              {SEVERITY_LABEL[question.severity]}
            </span>
            <span className="border-line min-w-0 truncate border-0 border-l border-solid pl-2">
              {question.assignee ? question.assignee.display_name : "Nobody yet"}
              {question.replaces_question_id && (
                <span className="text-warning"> · Revised last round</span>
              )}
            </span>
          </span>
        </span>
        <span
          className={cx(
            "text-meta flex shrink-0 items-center gap-1.5",
            ready ? "text-success font-semibold" : "text-ink-muted",
          )}
        >
          {ready && <Check aria-hidden="true" size={14} />}
          {ready ? "Answer ready" : questionStatusLabel(question.status)}
        </span>
      </summary>

      <div className="border-line grid gap-3 border-0 border-t border-solid p-4">
        {question.rationale && (
          <p className="text-ink-muted text-body m-0 max-w-[68ch]">{question.rationale}</p>
        )}
        <SourceLinks
          evidence={evidence}
          humanAnswers={humanEvidence(analysis, question.kind, question.subject)}
          subject={question.subject}
        />

        {/* Serif, like the question above it and like the same words once they
            are stored. The register split is how the product tells you whether
            you are reading the interface or the requirement, and it broke at
            the one moment a human contributes content. `field-sizing: content`
            lets the box grow instead of scrolling a 400-character answer
            through a two-line window. */}
        <Textarea
          className="text-document min-h-20 font-serif [field-sizing:content]"
          label="Your answer"
          onChange={(event) => onAnswer(event.target.value)}
          placeholder="Answer in business language — a partial answer can be saved as a draft."
          rows={3}
          value={answer}
        />

      <div className="border-line grid gap-2 rounded-sm border border-dashed p-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h4 className="text-label text-ink-muted m-0">Suggested answers, from the evidence</h4>
          <Button
            disabled={busy || suggestionsBusy}
            onClick={() => onSuggestAnswers?.(question)}
            size="sm"
            variant="text"
          >
            {loadingSuggestions ? "Looking…" : "Look again"}
          </Button>
        </div>
        {loadingSuggestions && (
          <p className="text-ink-muted text-body m-0" role="status">
            Checking this analysis and trusted knowledge…
          </p>
        )}
        {!suggestionSet && !loadingSuggestions && (
          <p className="text-ink-muted text-body m-0">
            None yet. Answer directly, or look again.
          </p>
        )}
        {suggestionSet && suggestionSet.suggestions.length === 0 && (
          <p className="text-ink-muted text-body m-0">
            Nothing in the evidence answers this. Answer directly.
          </p>
        )}
        {suggestionSet?.suggestions.map((suggestion) => {
          const picked = pickedSuggestion === suggestion.id;
          return (
            <button
              aria-pressed={picked}
              className={cx(
                "grid min-w-0 cursor-pointer gap-1.5 rounded-sm border border-solid p-3 text-left",
                TRANSITION,
                picked
                  ? "border-accent bg-accent-wash"
                  : cx("border-line-strong bg-surface", HOVER_GROUND),
                "disabled:cursor-not-allowed disabled:opacity-60",
              )}
              disabled={busy}
              key={suggestion.id}
              onClick={() => onPickSuggestion(suggestion.id, suggestion.answer)}
              type="button"
            >
              <span className="flex min-w-0 flex-wrap items-center gap-2">
                <Badge className="[&>span]:whitespace-normal" tone={picked ? "accent" : "neutral"}>
                  {SUGGESTION_SOURCE_LABEL[suggestion.source]}
                </Badge>
                {picked && (
                  <span className="text-accent text-label inline-flex items-center gap-1">
                    <Check aria-hidden="true" size={12} />
                    Using this
                  </span>
                )}
              </span>
              {/* Never truncated: a suggestion you have to commit to in order to
                  read is a suggestion you cannot judge. */}
              <span dir="auto" className="text-document text-ink max-w-[68ch] font-serif">
                {suggestion.answer}
              </span>
              {picked && (
                <>
                  <span className="text-ink-muted text-body">{suggestion.rationale}</span>
                  <span className="text-ink-muted text-meta">
                    {suggestion.evidence
                      .map(
                        (item) =>
                          `${evidenceFieldLabel(item.field)} · ${item.requirement_id.slice(0, 8)}`,
                      )
                      .join("; ")}
                  </span>
                </>
              )}
            </button>
          );
        })}
        {suggestionSet?.suggestions.filter(s => s.id === pickedSuggestion).flatMap(s => s.reference_evidence ?? []).map(c => (
          <div className="min-w-0 [overflow-wrap:anywhere]" key={`${c.publication_id}-${c.block_id}-${c.start_offset}`}>
            <p>Published reference — confirm that it applies before submitting this answer.</p>
            <a className="text-accent underline" target="_blank" rel="noreferrer" href={`/documents/library/${encodeURIComponent(c.document_id)}?${new URLSearchParams({ publication: c.publication_id, version: c.version_id, revision: c.revision_id, passage: c.block_id })}`}>
              {c.title} · version {c.version_number} · {c.location}
            </a>
            <blockquote dir="auto">{c.excerpt}</blockquote>
          </div>
        ))}
        {pickedSuggestion && (
          <p className="text-ink-muted text-meta m-0">
            Edit the wording freely — where it came from stays on the record.
          </p>
        )}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2">
        {question.draft_updated_by ? (
          <p className="text-ink-muted text-meta m-0">
            Draft saved by {question.draft_updated_by.display_name} ·{" "}
            {when(question.draft_updated_at)}
          </p>
        ) : (
          <span />
        )}
          <Button
            disabled={busy || !answer.trim()}
            onClick={() => onSaveDraft?.(question, answer)}
            size="sm"
          >
            Save as a draft
          </Button>
        </div>
        {/* Last, not first. An open row is read as the work — what is being
            asked, where it came from, the answer, the help — and these change
            how the question is filed, not what the answer is. First, they put
            the answer field ~380px below the question it answers (critique
            2026-09-21, P2). Still open rather than behind a second disclosure:
            the row above shows severity, owner and state, and these are the
            controls that change them. */}
        {(onClassify || onAssign) && (
          <div className="border-line grid gap-3 border-0 border-t border-solid pt-3 @[30rem]:grid-cols-2">
            <h4 className="text-label text-ink-muted m-0 @[30rem]:col-span-2">Triage</h4>
            {onClassify && (
              <>
                <Select
                  disabled={busy}
                  label="How much it matters"
                  onChange={(event) =>
                    onClassify(
                      question,
                      event.target.value as ClarificationSeverity,
                      question.is_blocker,
                    )
                  }
                  value={question.severity}
                >
                  <option value="low">{SEVERITY_LABEL.low}</option>
                  <option value="medium">{SEVERITY_LABEL.medium}</option>
                  <option value="high">{SEVERITY_LABEL.high}</option>
                </Select>
                <Checkbox
                  checked={question.is_blocker}
                  disabled={busy}
                  label="Blocks confirmation"
                  onChange={(event) =>
                    onClassify(question, question.severity, event.target.checked)
                  }
                />
              </>
            )}
            {onAssign && (
              <Select
                aria-label={`Who answers: ${question.subject}`}
                disabled={busy}
                label="Who answers"
                onChange={(event) => onAssign(question, event.target.value || null)}
                value={question.assignee?.id ?? ""}
              >
                <option value="">Nobody yet</option>
                {team.map((actor) => (
                  <option key={actor.id} value={actor.id}>
                    {actor.display_name}
                  </option>
                ))}
              </Select>
            )}
          </div>
        )}

      </div>
    </details>
  );
}
