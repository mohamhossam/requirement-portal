import { Plus } from "lucide-react";

import type { AcceptanceCriterion } from "../../api/client";
import { Button } from "../../components/ui/Button";
import { Textarea } from "../../components/ui/Input";

const FIELDS = [
  { key: "given", label: "Given" },
  { key: "when", label: "When" },
  { key: "then", label: "Then" },
] as const;

/**
 * Acceptance criteria as Given / When / Then fields, one group per criterion.
 *
 * Shared by the Story editor and the manual split and merge dialog, which each
 * drew their own `.criterion-row` grid. Each criterion is a named group, so a
 * screen reader hears "Criterion 2, Given" rather than a third unlabelled
 * "Given"; the three fields sit side by side from `md` and stack below it, and
 * the criterion text is set in the document serif, like the story it becomes.
 */
export function CriteriaFields({
  criteria,
  legend = "Acceptance criteria",
  onChange,
  onAdd,
  onRemove,
}: {
  criteria: AcceptanceCriterion[];
  legend?: string;
  onChange: (index: number, field: keyof AcceptanceCriterion, value: string) => void;
  onAdd: () => void;
  onRemove: (index: number) => void;
}) {
  return (
    <fieldset className="border-line m-0 grid min-w-0 gap-3 rounded-md border border-solid p-4">
      <legend className="text-label text-ink px-1">{legend}</legend>
      {criteria.map((criterion, index) => (
        <fieldset className="m-0 grid min-w-0 gap-2 border-0 p-0" key={index}>
          {/* The legend names the group only as the fieldset's first child, so it
              stays there, hidden; the visible label sits beside Remove. */}
          <legend className="sr-only">Criterion {index + 1}</legend>
          <div className="flex items-center justify-between gap-3">
            <span aria-hidden="true" className="text-meta text-ink-muted font-semibold">
              Criterion {index + 1}
            </span>
            <Button
              aria-label={`Remove acceptance criterion ${index + 1}`}
              disabled={criteria.length === 1}
              onClick={() => onRemove(index)}
              type="button"
              variant="text-danger"
            >
              Remove
            </Button>
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            {FIELDS.map((field) => (
              <Textarea
                className="font-serif text-document"
                key={field.key}
                label={field.label}
                onChange={(event) => onChange(index, field.key, event.target.value)}
                rows={2}
                value={criterion[field.key]}
              />
            ))}
          </div>
        </fieldset>
      ))}
      <Button className="w-fit" icon={<Plus aria-hidden="true" size={16} />} onClick={onAdd} type="button" variant="secondary">
        Add criterion
      </Button>
    </fieldset>
  );
}
