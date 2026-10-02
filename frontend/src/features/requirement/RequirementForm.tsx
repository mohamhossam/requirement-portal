import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from "react";

import type { RequirementDraftInput, RequirementInput } from "../../api/client";
import { useUnsavedGuard } from "../../app/useUnsavedChanges";
import { Disclosure } from "../../components/Disclosure";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Button, cx, Input, Textarea } from "../../components/ui";

type FormValue = RequirementDraftInput;

type Props = {
  initial?: Partial<RequirementInput>;
  submitLabel: string;
  secondarySubmitLabel?: string;
  busy?: boolean;
  error?: string | null;
  onSubmit: (input: FormValue, intent: "primary" | "secondary") => void;
  onChange?: (input: FormValue) => void;
  onCancel?: () => void;
  context?: "create" | "edit";
  attachments?: ReactNode;
  hasIncludedAttachment?: boolean;
  attachmentsBusy?: boolean;
  attachmentsBlocked?: boolean;
  /** Draft save state, shown beside the save buttons rather than in a rail. */
  status?: ReactNode;
  /**
   * Whether analysis can start, in the owner's words, beside the button it
   * gates. When attachments hold the submit, the button is gated *by* this
   * element (`readinessId`) rather than disabled, so the reason stays reachable.
   */
  readiness?: ReactNode;
  readinessId?: string;
  /** Shown under the business need below `lg`; the page puts it beside the form above. */
  example?: ReactNode;
};

type FieldErrors = {
  title?: string;
  description?: string;
};

const emptyValue: FormValue = {
  title: "",
  description: "",
  desired_outcome: "",
  customer_context: "",
  channels: [],
  systems: [],
  business_rules: [],
  constraints: [],
};

const rows = (values?: string[] | null) => (values ?? []).join("\n");
const values = (raw: string) => raw.split("\n").map((item) => item.trim()).filter(Boolean);

export function RequirementForm({
  initial,
  submitLabel,
  secondarySubmitLabel,
  busy,
  error,
  onSubmit,
  onChange,
  onCancel,
  context = "edit",
  attachments,
  hasIncludedAttachment = false,
  attachmentsBusy = false,
  attachmentsBlocked = false,
  status,
  readiness,
  readinessId,
  example,
}: Props) {
  const [form, setForm] = useState<FormValue>({
    ...emptyValue,
    ...initial,
    desired_outcome: initial?.desired_outcome ?? "",
    customer_context: initial?.customer_context ?? "",
    channels: initial?.channels ?? [],
    systems: initial?.systems ?? [],
    business_rules: initial?.business_rules ?? [],
    constraints: initial?.constraints ?? [],
  });
  // The create flow autosaves a draft, so only the edit context can lose work.
  useUnsavedGuard(form, context === "edit");
  const [validation, setValidation] = useState<FieldErrors>({});
  const fieldId = useId();
  const validationRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (validation.title || validation.description) {
      validationRef.current?.focus();
    }
  }, [validation]);

  const change = (patch: Partial<FormValue>) => {
    const next = { ...form, ...patch };
    setForm(next);
    onChange?.(next);
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const submitter = (event.nativeEvent as SubmitEvent).submitter as HTMLButtonElement | null;
    const intent = submitter?.value === "secondary" ? "secondary" : "primary";
    if (attachmentsBusy || (intent === "primary" && attachmentsBlocked)) return;
    const nextValidation: FieldErrors = {};
    if (intent === "primary" || context === "edit") {
      if (!form.title.trim()) nextValidation.title = "Add a short title for this requirement.";
      if (!form.description.trim() && !hasIncludedAttachment) {
        nextValidation.description = attachments
          ? "Describe the business need or attach a ready file before continuing."
          : "Describe the business need before continuing.";
      }
    }
    if (Object.keys(nextValidation).length) {
      setValidation(nextValidation);
      return;
    }
    setValidation({});
    onSubmit(
      {
        ...form,
        title: form.title.trim(),
        description: form.description.trim(),
        desired_outcome: form.desired_outcome.trim(),
        customer_context: form.customer_context.trim(),
      },
      intent,
    );
  };

  const create = context === "create";
  const optionalFilled = Boolean(
    form.desired_outcome.trim() || form.customer_context.trim() ||
    form.channels.length || form.systems.length || form.business_rules.length || form.constraints.length,
  );
  const missing = !form.title.trim() || (!form.description.trim() && !hasIncludedAttachment);
  // Attachments still processing, or one that could not be read, hold the
  // submit: the handler returns early for both. Say so instead of disabling.
  const attachmentHold = attachmentsBusy || attachmentsBlocked;
  const holdReason = attachmentsBusy ? "Files are still processing." : "A file needs attention first.";

  const listField = (
    name: "channels" | "systems" | "business_rules" | "constraints",
    label: string,
    hint: string,
  ) => (
    <Textarea
      hint={hint}
      id={`${fieldId}-${name}`}
      label={label}
      onChange={(event) => change({ [name]: values(event.target.value) })}
      rows={3}
      value={rows(form[name])}
    />
  );

  return (
    <form className="grid min-w-0 gap-6" onSubmit={submit} noValidate>
      {(validation.title || validation.description) && (
        // Not an alert: it takes focus, which announces it, and each field's
        // own error is already one. Three alerts at once read as one garble.
        <div
          aria-labelledby={`${fieldId}-summary`}
          className="border-line bg-danger-wash grid gap-2 rounded-md border border-solid border-l-[3px] border-l-[var(--danger)] px-4 py-3"
          role="group"
          tabIndex={-1}
          ref={validationRef}
        >
          <strong className="text-danger text-body" id={`${fieldId}-summary`}>Check the requirement details</strong>
          <ul className="m-0 grid gap-1 pl-5">
            {validation.title && <li><a className="text-danger text-body underline underline-offset-2" href={`#${fieldId}-title`}>{validation.title}</a></li>}
            {validation.description && <li><a className="text-danger text-body underline underline-offset-2" href={`#${fieldId}-description`}>{validation.description}</a></li>}
          </ul>
        </div>
      )}

      {/* Title and need first: they are all analysis requires. The numbered
          legends ("01 Describe the need", "02 Add known context", "03 Record
          boundaries") described no order anybody had to follow, and were read
          aloud as "zero one". */}
      <div className="grid gap-5">
        <Input
          className="max-w-[var(--measure-interface)]"
          autoFocus={create}
          error={validation.title}
          hint="A short name people will recognise, like “High-speed business bundles”."
          id={`${fieldId}-title`}
          label="Requirement title"
          onChange={(event) => {
            change({ title: event.target.value });
            if (validation.title) setValidation((current) => ({ ...current, title: undefined }));
          }}
          required
          value={form.title}
        />
        <Textarea
          error={validation.description}
          hint={attachments
            ? "What should change, for whom, and why, in your own words. You can attach files instead, or as well."
            : "What should change, for whom, and why, in your own words."}
          id={`${fieldId}-description`}
          label="Business need"
          onChange={(event) => {
            change({ description: event.target.value });
            if (validation.description) setValidation((current) => ({ ...current, description: undefined }));
          }}
          // A ready file included in analysis carries the need on its own.
          required={!hasIncludedAttachment}
          rows={create ? 7 : 5}
          value={form.description}
        />
        {example}
        {attachments}
      </div>

      <Disclosure defaultOpen={optionalFilled || !create} label="Add detail if you know it (optional)">
        <div className="grid gap-5 pt-2">
          <p className="text-meta text-ink-muted m-0 max-w-[var(--measure-interface)]">
            Leave anything you are unsure of blank. The analysis asks about what is missing rather than guessing.
          </p>
          <Input
            className="max-w-[var(--measure-interface)]"
            hint="What should be possible afterwards? Leave it blank and the analysis will suggest one."
            id={`${fieldId}-desired_outcome`}
            label="Desired outcome"
            onChange={(event) => change({ desired_outcome: event.target.value })}
            value={form.desired_outcome}
          />
          <Input
            className="max-w-[var(--measure-interface)]"
            hint="The customers or teams this changes things for."
            id={`${fieldId}-customer_context`}
            label="Who is affected"
            onChange={(event) => change({ customer_context: event.target.value })}
            value={form.customer_context}
          />
          {/* Two columns on the page; one in the 480px drawer, where two squeezed
              the hints onto different line counts and the fields out of line. */}
          <div className={cx("grid gap-5", create && "sm:grid-cols-2")}>
            {listField("channels", "Channels", "Where customers will use it, one per line: Web, Assisted sales.")}
            {listField("systems", "Systems involved", "One per line. Only systems you know are involved; leave it blank rather than guess.")}
            {listField("business_rules", "Rules that must hold", "One per line, only rules someone has actually stated.")}
            {listField("constraints", "Deadlines and limits", "One per line: dates, compliance, capacity.")}
          </div>
        </div>
      </Disclosure>

      {error && <ErrorNotice message={error} />}
      {/* Sticky in the create flow only, and only from `sm`: at 390 a pinned
          bar was 180px, a fifth of the screen, and hid the focused field
          (WCAG 2.4.11). `html:has([data-intake-actions])` reserves its height
          in the scroll padding, so a field tabbed to lands above it. */}
      <div
        className={cx(
          "grid gap-3",
          create && "bg-canvas py-3 [border-top:1px_solid_var(--line)] sm:sticky sm:bottom-0 sm:z-[var(--z-sticky)]",
        )}
        data-intake-actions={create || undefined}
      >
        <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
          <div className="grid min-w-0 gap-1">
            {readiness}
            {status}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {onCancel && <Button variant="text" type="button" onClick={onCancel}>Cancel</Button>}
            {secondarySubmitLabel && (
              <Button
                blockedBy={attachmentsBusy && readinessId ? readinessId : undefined}
                disabled={busy || (attachmentsBusy && !readinessId)}
                type="submit"
                value="secondary"
                variant="secondary"
              >
                {secondarySubmitLabel}
              </Button>
            )}
            <Button
              aria-describedby={readinessId}
              blockedBy={attachmentHold && readinessId ? readinessId : undefined}
              blockedReason={attachmentHold && !readinessId ? holdReason : undefined}
              loading={busy}
              loadingLabel="Saving…"
              type="submit"
              value="primary"
              // The accent goes to the act only when it will go through. Short
              // of that it is still pressable: pressing it runs the validation
              // above and says what is missing, beside each field.
              variant={missing || attachmentHold ? "secondary" : "primary"}
            >
              {submitLabel}
            </Button>
          </div>
        </div>
      </div>
    </form>
  );
}
