import { useId, useState, type FormEvent } from "react";

import type { AcceptanceCriterion, Story, StoryInput } from "../../api/client";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Modal, ModalBody, ModalFooter, ModalHeader } from "../../components/Modal";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { CriteriaFields } from "./CriteriaFields";

type Props = {
  operation: "split" | "merge";
  sources: Story[];
  busy: boolean;
  error: string | null;
  onSubmit: (drafts: StoryInput[]) => void;
  onCancel: () => void;
};

const copyStory = (story: Story): StoryInput => ({
  role: story.role,
  action: story.action,
  value: story.value,
  acceptance_criteria: story.acceptance_criteria.map((item) => ({ ...item })),
});

const blankCriterion = (): AcceptanceCriterion => ({ given: "", when: "", then: "" });

export function ManualStoryChangeDialog({
  operation,
  sources,
  busy,
  error,
  onSubmit,
  onCancel,
}: Props) {
  const [drafts, setDrafts] = useState<StoryInput[]>(() =>
    operation === "split"
      ? [copyStory(sources[0]!), copyStory(sources[0]!)]
      : [copyStory(sources[0]!)],
  );
  const [validation, setValidation] = useState<string | null>(null);

  const updateDraft = (index: number, field: "role" | "action" | "value", value: string) =>
    setDrafts((current) =>
      current.map((draft, draftIndex) =>
        draftIndex === index ? { ...draft, [field]: value } : draft,
      ),
    );

  const updateCriterion = (
    draftIndex: number,
    criterionIndex: number,
    field: keyof AcceptanceCriterion,
    value: string,
  ) =>
    setDrafts((current) =>
      current.map((draft, index) =>
        index === draftIndex
          ? {
              ...draft,
              acceptance_criteria: draft.acceptance_criteria.map((criterion, itemIndex) =>
                itemIndex === criterionIndex ? { ...criterion, [field]: value } : criterion,
              ),
            }
          : draft,
      ),
    );

  const addCriterion = (draftIndex: number) =>
    setDrafts((current) =>
      current.map((draft, index) =>
        index === draftIndex
          ? { ...draft, acceptance_criteria: [...draft.acceptance_criteria, blankCriterion()] }
          : draft,
      ),
    );

  const removeCriterion = (draftIndex: number, criterionIndex: number) =>
    setDrafts((current) =>
      current.map((draft, index) =>
        index === draftIndex
          ? {
              ...draft,
              acceptance_criteria: draft.acceptance_criteria.filter(
                (_, itemIndex) => itemIndex !== criterionIndex,
              ),
            }
          : draft,
      ),
    );

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const cleaned = drafts.map((draft) => ({
      role: draft.role.trim(),
      action: draft.action.trim(),
      value: draft.value.trim(),
      acceptance_criteria: draft.acceptance_criteria.map((criterion) => ({
        given: criterion.given.trim(),
        when: criterion.when.trim(),
        then: criterion.then.trim(),
      })),
    }));
    if (cleaned.some((draft) => !draft.role || !draft.action || !draft.value)) {
      setValidation("Every replacement Story needs a role, action and value.");
      return;
    }
    if (
      cleaned.some(
        (draft) =>
          draft.acceptance_criteria.length === 0 ||
          draft.acceptance_criteria.some(
            (criterion) => !criterion.given || !criterion.when || !criterion.then,
          ),
      )
    ) {
      setValidation("Every replacement Story needs a complete Given, When and Then.");
      return;
    }
    onSubmit(cleaned);
  };

  const title = operation === "split" ? "Manually split Story" : "Manually merge Stories";
  const titleId = useId();
  return (
    <Modal labelledBy={titleId} onClose={onCancel} size="wide" variant="dialog">
      <form onSubmit={submit}>
        {/* A person writes these, so the dialog says so in its description
            rather than in an uppercase kicker above the title. */}
        <ModalHeader
          description={
            operation === "split"
              ? "Write the two Stories that replace it, by hand. The first keeps the original identity."
              : "Write the one Story that replaces them, by hand. The earliest selected Story keeps its identity."
          }
          id={titleId}
          title={title}
        />
        <ModalBody>
          {drafts.map((draft, draftIndex) => (
            <fieldset className="border-line m-0 grid min-w-0 gap-4 rounded-md border border-solid p-4" key={draftIndex}>
              <legend className="text-title text-ink px-1">Replacement Story {draftIndex + 1}</legend>
              <div className="grid gap-4 md:grid-cols-3">
                <Input
                  autoFocus={draftIndex === 0}
                  label="As a"
                  onChange={(event) => updateDraft(draftIndex, "role", event.target.value)}
                  value={draft.role}
                />
                <Input
                  label="I want"
                  onChange={(event) => updateDraft(draftIndex, "action", event.target.value)}
                  value={draft.action}
                />
                <Input
                  label="So that"
                  onChange={(event) => updateDraft(draftIndex, "value", event.target.value)}
                  value={draft.value}
                />
              </div>
              <CriteriaFields
                criteria={draft.acceptance_criteria}
                onAdd={() => addCriterion(draftIndex)}
                onChange={(criterionIndex, field, value) => updateCriterion(draftIndex, criterionIndex, field, value)}
                onRemove={(criterionIndex) => removeCriterion(draftIndex, criterionIndex)}
              />
            </fieldset>
          ))}
          {(validation || error) && <ErrorNotice message={validation ?? error ?? ""} />}
        </ModalBody>
        <ModalFooter>
          <Button variant="secondary" type="button" onClick={onCancel}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" disabled={busy}>
            {busy ? "Saving…" : operation === "split" ? "Apply manual split" : "Apply manual merge"}
          </Button>
        </ModalFooter>
      </form>
    </Modal>
  );
}
