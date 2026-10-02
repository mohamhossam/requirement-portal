import { useState, type FormEvent } from "react";

import type { Epic, EpicInput } from "../../api/client";
import { ErrorNotice } from "../../components/ErrorNotice";
import { useUnsavedGuard } from "../../app/useUnsavedChanges";
import { Button } from "../../components/ui/Button";
import { Checkbox } from "../../components/ui/Checkbox";
import { Input, Textarea } from "../../components/ui/Input";

export function EpicEditForm({ epic, busy, error, onSave, onCancel }: {
  epic: Epic;
  busy: boolean;
  error: string | null;
  onSave: (input: EpicInput) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(epic.name);
  const [outcome, setOutcome] = useState(epic.outcome);
  const [businessCase, setBusinessCase] = useState(epic.business_case);
  useUnsavedGuard({ name, outcome, businessCase });
  const [validation, setValidation] = useState<string | null>(null);
  const [reconciledVersion, setReconciledVersion] = useState<number | null>(null);
  const sourceReconciled = reconciledVersion === epic.version;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (![name, outcome, businessCase].every((value) => value.trim())) {
      setValidation("Name, outcome and business case are all required.");
      return;
    }
    if (epic.stale && !sourceReconciled) {
      setValidation("Acknowledge that this edit reconciles the current source before saving.");
      return;
    }
    onSave({ name: name.trim(), outcome: outcome.trim(), business_case: businessCase.trim(), source_reconciled: sourceReconciled });
  };

  return (
    <form className="grid gap-4" onSubmit={submit}>
      <Input label="Epic name" onChange={(event) => setName(event.target.value)} value={name} />
      <Textarea label="Business outcome" onChange={(event) => setOutcome(event.target.value)} rows={3} value={outcome} />
      <Textarea label="Business case" onChange={(event) => setBusinessCase(event.target.value)} rows={3} value={businessCase} />
      {epic.stale && (
        <Checkbox
          checked={sourceReconciled}
          label="I reviewed the current source and this edit reconciles the Epic."
          onChange={(event) => setReconciledVersion(event.target.checked ? epic.version : null)}
        />
      )}
      {(validation || error) && <ErrorNotice message={validation ?? error ?? ""} />}
      <div className="flex flex-wrap justify-end gap-2">
        <Button variant="secondary" type="button" onClick={onCancel}>Cancel</Button>
        <Button variant="primary" type="submit" disabled={busy}>{busy ? "Saving…" : "Save Epic"}</Button>
      </div>
    </form>
  );
}
