import { useState, type FormEvent } from "react";

import type { AcceptanceCriterion, Story, StoryInput } from "../../api/client";
import { ErrorNotice } from "../../components/ErrorNotice";
import { useUnsavedGuard } from "../../app/useUnsavedChanges";
import { Button } from "../../components/ui/Button";
import { Checkbox } from "../../components/ui/Checkbox";
import { Input } from "../../components/ui/Input";
import { CriteriaFields } from "./CriteriaFields";

const blankCriterion = (): AcceptanceCriterion => ({ given: "", when: "", then: "" });

export function StoryEditForm({
  story,
  busy,
  error,
  onSave,
  onCancel,
}: {
  story: Story;
  busy: boolean;
  error: string | null;
  onSave: (input: StoryInput) => void;
  onCancel: () => void;
}) {
  const [role, setRole] = useState(story.role);
  const [action, setAction] = useState(story.action);
  const [value, setValue] = useState(story.value);
  const [criteria, setCriteria] = useState<AcceptanceCriterion[]>(
    story.acceptance_criteria.map((item) => ({ ...item })),
  );
  useUnsavedGuard({ role, action, value, criteria });
  const [validation, setValidation] = useState<string | null>(null);
  const [reconciledVersion, setReconciledVersion] = useState<number | null>(null);
  const sourceReconciled = reconciledVersion === story.version;

  const setCriterion = (index: number, field: keyof AcceptanceCriterion, next: string) =>
    setCriteria((current) =>
      current.map((item, itemIndex) =>
        itemIndex === index ? { ...item, [field]: next } : item,
      ),
    );
  const addCriterion = () => setCriteria((current) => [...current, blankCriterion()]);
  const removeCriterion = (index: number) =>
    setCriteria((current) => current.filter((_, itemIndex) => itemIndex !== index));

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (![role, action, value].every((field) => field.trim())) {
      setValidation("Role, action and value are all required.");
      return;
    }
    const cleaned = criteria
      .map((item) => ({ given: item.given.trim(), when: item.when.trim(), then: item.then.trim() }))
      .filter((item) => item.given || item.when || item.then);
    if (cleaned.length === 0) {
      setValidation("A Story needs at least one acceptance criterion.");
      return;
    }
    if (!cleaned.every((item) => item.given && item.when && item.then)) {
      setValidation("Every acceptance criterion needs a Given, a When and a Then.");
      return;
    }
    if (story.stale && !sourceReconciled) {
      setValidation("Acknowledge that this edit reconciles the current source before saving.");
      return;
    }
    onSave({
      role: role.trim(),
      action: action.trim(),
      value: value.trim(),
      acceptance_criteria: cleaned,
      source_reconciled: sourceReconciled,
    });
  };

  return (
    <form className="story-editor grid gap-4" onSubmit={submit}>
      <div className="grid gap-4 sm:grid-cols-2">
        <Input label="As a" onChange={(event) => setRole(event.target.value)} value={role} />
        <Input label="I want" onChange={(event) => setAction(event.target.value)} value={action} />
      </div>
      <Input label="So that" onChange={(event) => setValue(event.target.value)} value={value} />
      <CriteriaFields
        criteria={criteria}
        onAdd={addCriterion}
        onChange={setCriterion}
        onRemove={removeCriterion}
      />
      {story.stale && (
        <Checkbox
          checked={sourceReconciled}
          label="I reviewed the current Feature/source and this edit reconciles the Story."
          onChange={(event) => setReconciledVersion(event.target.checked ? story.version : null)}
        />
      )}
      {(validation || error) && <ErrorNotice message={validation ?? error ?? ""} />}
      <div className="flex flex-wrap justify-end gap-2">
        <Button variant="secondary" type="button" onClick={onCancel}>
          Cancel
        </Button>
        <Button variant="primary" type="submit" disabled={busy}>
          {busy ? "Saving…" : "Save Story"}
        </Button>
      </div>
    </form>
  );
}
