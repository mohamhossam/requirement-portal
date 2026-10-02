import { useState, type FormEvent } from "react";

import type { Feature, FeatureInput } from "../../api/client";
import { PATTERN_LABEL } from "./splittingPatterns";
import { ErrorNotice } from "../../components/ErrorNotice";
import { useUnsavedGuard } from "../../app/useUnsavedChanges";
import { Button } from "../../components/ui/Button";
import { Checkbox } from "../../components/ui/Checkbox";
import { Input, Textarea } from "../../components/ui/Input";
import { Select } from "../../components/ui/Select";

const patterns: FeatureInput["splitting_pattern"][] = [
  "component_system", "journey_stage", "mvp_vs_later", "channel", "business_variant",
];

export function FeatureEditForm({ feature, busy, error, onSave, onCancel }: {
  feature: Feature;
  busy: boolean;
  error: string | null;
  onSave: (input: FeatureInput) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(feature.name);
  const [outcome, setOutcome] = useState(feature.outcome);
  const [drop, setDrop] = useState(feature.delivery_drop);
  const [pattern, setPattern] = useState(feature.splitting_pattern);
  const [rationale, setRationale] = useState(feature.splitting_rationale);
  useUnsavedGuard({ name, outcome, drop, pattern, rationale });
  const [validation, setValidation] = useState<string | null>(null);
  const [reconciledVersion, setReconciledVersion] = useState<number | null>(null);
  const sourceReconciled = reconciledVersion === feature.version;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (![name, outcome, rationale].every((value) => value.trim())) {
      setValidation("Name, outcome and splitting rationale are required.");
      return;
    }
    if (feature.stale && !sourceReconciled) {
      setValidation("Acknowledge that this edit reconciles the current source before saving.");
      return;
    }
    onSave({ name: name.trim(), outcome: outcome.trim(), delivery_drop: drop, splitting_pattern: pattern, splitting_rationale: rationale.trim(), source_reconciled: sourceReconciled });
  };

  return (
    <form className="grid gap-4" onSubmit={submit}>
      <Input label="Feature name" onChange={(event) => setName(event.target.value)} value={name} />
      <Textarea label="Measurable outcome" onChange={(event) => setOutcome(event.target.value)} rows={3} value={outcome} />
      <div className="grid gap-4 sm:grid-cols-2">
        <Select label="Delivery drop" onChange={(event) => setDrop(event.target.value as FeatureInput["delivery_drop"])} value={drop}>
          <option value="mvp">MVP</option>
          <option value="later">Later</option>
        </Select>
        <Select label="Splitting pattern" onChange={(event) => setPattern(event.target.value as FeatureInput["splitting_pattern"])} value={pattern}>
          {patterns.map((value) => <option key={value} value={value}>{PATTERN_LABEL[value]}</option>)}
        </Select>
      </div>
      <Textarea label="Splitting rationale" onChange={(event) => setRationale(event.target.value)} rows={3} value={rationale} />
      {feature.stale && (
        <Checkbox
          checked={sourceReconciled}
          label="I reviewed the current Epic/source and this edit reconciles the Feature."
          onChange={(event) => setReconciledVersion(event.target.checked ? feature.version : null)}
        />
      )}
      {(validation || error) && <ErrorNotice message={validation ?? error ?? ""} />}
      <div className="flex flex-wrap justify-end gap-2">
        <Button variant="secondary" type="button" onClick={onCancel}>Cancel</Button>
        <Button variant="primary" type="submit" disabled={busy}>{busy ? "Saving…" : "Save Feature"}</Button>
      </div>
    </form>
  );
}
