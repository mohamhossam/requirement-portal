import { X } from "lucide-react";
import { useEffect, useId, useRef, useState, type ClipboardEvent, type KeyboardEvent, type ReactNode } from "react";

import { cx } from "./cx";
import { describedBy } from "./describedBy";
import { FieldShell } from "./Field";
import { CONTROL_BASE, FOCUS_RING, TARGET_MIN, TRANSITION } from "./recipes";
import { SEPARATOR, withDraft } from "./tagList";

export type TagInputProps = {
  label: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  required?: boolean;
  values: string[];
  onChange: (values: string[]) => void;
  /**
   * The text typed but not yet committed. Owned by the caller so that a form
   * can save it with `withDraft` — typing a name and pressing Save should not
   * lose it because nobody pressed Enter first.
   */
  draft: string;
  onDraftChange: (draft: string) => void;
  placeholder?: string;
  dir?: "auto" | "ltr" | "rtl";
  id?: string;
  fieldClassName?: string;
};

/**
 * A list of short entries, one chip each (§11): other names, matching phrases.
 *
 * Enter or a comma commits; pasting a list splits it; Backspace on an empty
 * field takes the last chip back into the field to be corrected. Each chip has
 * its own named remove button at the 24px floor, so a person can remove one
 * entry without retyping the rest — the reason this replaces "separate with
 * commas" in a plain input.
 *
 * Removing a chip moves focus to the chip that took its place, or to the field
 * when none is left, and says what went: the button a keyboard user pressed no
 * longer exists, and focus must not fall back to the page (WCAG 2.4.3).
 */
export function TagInput({
  label, hint, error, required, values, onChange, draft, onDraftChange, placeholder, dir, id, fieldClassName,
}: TagInputProps) {
  const generated = useId();
  const fieldId = id ?? generated;
  const hintId = `${fieldId}-hint`;
  const errorId = `${fieldId}-error`;
  const input = useRef<HTMLInputElement>(null);
  const list = useRef<HTMLUListElement>(null);
  // Which chip to focus after a removal re-renders the list; -1 means the field.
  const focusAfter = useRef<number | null>(null);
  const [announcement, setAnnouncement] = useState("");

  useEffect(() => {
    if (focusAfter.current === null) return;
    const buttons = list.current?.querySelectorAll<HTMLButtonElement>("button") ?? [];
    const target = focusAfter.current < 0 ? null : buttons[Math.min(focusAfter.current, buttons.length - 1)];
    (target ?? input.current)?.focus();
    focusAfter.current = null;
  });

  const remove = (index: number) => {
    const removed = values[index];
    onChange(values.filter((_, position) => position !== index));
    focusAfter.current = values.length > 1 ? index : -1;
    setAnnouncement(`Removed ${removed}.`);
  };

  const commit = () => {
    if (!draft.trim()) return;
    onChange(withDraft(values, draft));
    onDraftChange("");
  };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter" || event.key === ",") {
      // Enter would otherwise submit the whole form mid-list.
      event.preventDefault();
      commit();
    } else if (event.key === "Backspace" && draft === "" && values.length > 0) {
      event.preventDefault();
      const last = values.at(-1) ?? "";
      onDraftChange(last);
      onChange(values.slice(0, -1));
      setAnnouncement(`${last} is back in the field to edit.`);
    }
  };

  const onPaste = (event: ClipboardEvent<HTMLInputElement>) => {
    const text = event.clipboardData.getData("text");
    if (!SEPARATOR.test(text)) return;
    event.preventDefault();
    onChange(withDraft(values, `${draft}${text}`));
    onDraftChange("");
  };

  return (
    <FieldShell
      className={fieldClassName}
      error={error}
      errorId={errorId}
      hint={hint}
      hintId={hintId}
      id={fieldId}
      label={label}
      required={required}
    >
      <div className="grid gap-2">
        {values.length > 0 && (
          <ul ref={list} role="list" className="m-0 flex list-none flex-wrap gap-1.5 p-0">
            {values.map((value, index) => (
              <li key={value}
                className="bg-surface-sunken text-ink text-meta border-line inline-flex max-w-full items-center gap-1 rounded-sm border border-solid py-0.5 pr-1 pl-2">
                <span className="truncate" dir={dir}>{value}</span>
                <button type="button" aria-label={`Remove ${value}`}
                  className={cx(
                    "text-ink-muted hover:text-ink grid cursor-pointer place-items-center rounded-sm border-0 bg-transparent p-0",
                    "hover:[background-color:color-mix(in_srgb,var(--accent)_12%,var(--surface-sunken))]",
                    TARGET_MIN, FOCUS_RING, TRANSITION,
                  )}
                  onClick={() => remove(index)}>
                  <X size={14} aria-hidden="true" />
                </button>
              </li>
            ))}
          </ul>
        )}
        <input
          ref={input}
          id={fieldId}
          dir={dir}
          value={draft}
          placeholder={placeholder}
          aria-describedby={describedBy(hint, hintId, error, errorId)}
          aria-invalid={error ? true : undefined}
          className={CONTROL_BASE}
          onChange={(event) => {
            const text = event.target.value;
            if (SEPARATOR.test(text)) {
              onChange(withDraft(values, text));
              onDraftChange("");
            } else {
              onDraftChange(text);
            }
          }}
          onKeyDown={onKeyDown}
          onPaste={onPaste}
          onBlur={commit}
        />
        <span className="sr-only" role="status">{announcement}</span>
      </div>
    </FieldShell>
  );
}
