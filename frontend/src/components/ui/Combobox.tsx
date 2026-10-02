import { Check, LoaderCircle, Search, X } from "lucide-react";
import { useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";

import { cx } from "./cx";
import { FieldShell } from "./Field";
import { CONTROL_BASE, FOCUS_RING, HOVER_GROUND, TARGET_MIN, TRANSITION } from "./recipes";

export type ComboboxOption = {
  id: string;
  label: string;
  /** A second line — an owner, an email, a short ID. */
  meta?: ReactNode;
};

/**
 * Pick one thing by typing part of its name (WAI-ARIA 1.2 combobox, list
 * autocomplete).
 *
 * It exists because a person cannot type a UUID from memory (docs/ux-plan.md
 * §3.8), and a native `<select>` cannot search a list the server has to filter.
 * Presentation only: the caller owns the query text, fetches the options for it
 * and decides what a choice means. This draws the field, the list and the
 * keyboard model — ↓/↑ move, Enter picks, Escape closes then clears the text —
 * and keeps focus on the input the whole time, with the highlighted option
 * named through `aria-activedescendant`.
 *
 * When something is chosen, its name sits in the field and a 24px clear button
 * appears beside it; typing again replaces the choice with a search.
 */
export function Combobox({
  label,
  hint,
  placeholder,
  selected,
  query,
  onQueryChange,
  options,
  loading = false,
  emptyText = "No matches",
  onSelect,
  fieldClassName,
}: {
  label: ReactNode;
  hint?: ReactNode;
  placeholder?: string;
  /** The current choice, or null for "any". */
  selected: ComboboxOption | null;
  query: string;
  onQueryChange: (value: string) => void;
  options: ComboboxOption[];
  loading?: boolean;
  emptyText?: string;
  onSelect: (option: ComboboxOption | null) => void;
  fieldClassName?: string;
}) {
  const id = useId();
  const listId = `${id}-list`;
  const hintId = `${id}-hint`;
  const inputRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  // Nothing is highlighted until the person moves into the list, so Enter on a
  // field they have only just reached never applies a choice they did not make.
  const [active, setActive] = useState(-1);

  // The field shows the choice until the person starts typing over it.
  const text = editing || !selected ? query : selected.label;
  const searching = query.trim().length > 0;
  const expanded = open && options.length > 0;
  const noMatch = open && !loading && options.length === 0 && searching;

  // Kept inside whatever list is showing now, so a shorter result never leaves
  // the highlight pointing past the end.
  const current = active < 0 || options.length === 0 ? -1 : Math.min(active, options.length - 1);

  const close = () => {
    setOpen(false);
    setEditing(false);
    setActive(-1);
    onQueryChange("");
  };

  const choose = (option: ComboboxOption) => {
    onSelect(option);
    close();
  };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setOpen(true);
      // Alt+↓ opens the list without moving into it (WAI-ARIA combobox).
      if (!event.altKey) setActive(Math.min(options.length - 1, current + 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      if (open) setActive(Math.max(0, current - 1));
    } else if (event.key === "Enter" && expanded && options[current]) {
      event.preventDefault();
      choose(options[current]);
    } else if (event.key === "Escape") {
      if (open || editing) {
        event.preventDefault();
        close();
      }
    }
  };

  const clear = () => {
    onSelect(null);
    close();
    inputRef.current?.focus();
  };

  return (
    <FieldShell className={fieldClassName} errorId={`${id}-error`} hint={hint} hintId={hintId} id={id} label={label}>
      <span className="relative block">
        <Search
          aria-hidden="true"
          className="text-ink-muted pointer-events-none absolute top-1/2 left-3 -translate-y-1/2"
          size={16}
        />
        <input
          ref={inputRef}
          aria-activedescendant={expanded && current >= 0 ? `${id}-option-${current}` : undefined}
          aria-autocomplete="list"
          aria-controls={listId}
          aria-describedby={hint ? hintId : undefined}
          aria-expanded={expanded}
          autoComplete="off"
          className={cx(CONTROL_BASE, "pl-9", selected && !editing ? "pr-10 font-semibold" : "pr-9")}
          id={id}
          // Option clicks keep focus here (their mousedown is cancelled), so a
          // blur is always the person leaving: close at once, with nothing left
          // open over the next control.
          onBlur={close}
          onChange={(event) => {
            // Over a chosen name, what was typed starts a new search rather than
            // editing the name in the middle.
            const typed = !editing && selected ? ((event.nativeEvent as InputEvent).data ?? "") : event.target.value;
            setEditing(true);
            setOpen(true);
            setActive(-1);
            onQueryChange(typed);
          }}
          onClick={() => setOpen(true)}
          onFocus={(event) => {
            if (selected && !editing) event.currentTarget.select();
          }}
          onKeyDown={onKeyDown}
          placeholder={placeholder}
          role="combobox"
          spellCheck={false}
          type="text"
          value={text}
        />
        <span className="absolute inset-y-0 right-1.5 grid place-items-center">
          {loading ? (
            <LoaderCircle aria-hidden="true" className="text-ink-muted mr-1.5 animate-spin motion-reduce:animate-none" size={16} />
          ) : selected && !editing ? (
            <button
              aria-label={`Clear ${typeof label === "string" ? label.toLowerCase() : "choice"}`}
              className={cx(
                TARGET_MIN,
                "text-ink-muted hover:text-ink grid cursor-pointer place-items-center rounded-sm border-0 bg-transparent p-0",
                HOVER_GROUND,
                TRANSITION,
                FOCUS_RING,
              )}
              onClick={clear}
              type="button"
            >
              <X aria-hidden="true" size={16} />
            </button>
          ) : null}
        </span>
        <ul
          aria-label={typeof label === "string" ? label : undefined}
          className={cx(
            POPOVER,
            "max-h-72 list-none overflow-y-auto p-1",
            !expanded && "hidden",
          )}
          id={listId}
          onMouseDown={(event) => event.preventDefault()}
          role="listbox"
          // A list taller than its box is a scroller, and Chrome puts scrollers
          // in the tab order; this one is driven from the field instead.
          tabIndex={-1}
        >
          {options.map((option, index) => {
            const chosen = selected?.id === option.id;
            return (
              <li
                key={option.id}
                aria-selected={index === current}
                className={cx(
                  "text-body text-ink grid min-h-9 cursor-pointer grid-cols-[1rem_minmax(0,1fr)] items-start gap-2 rounded-sm px-2 py-1.5",
                  index === current && "[background-color:color-mix(in_srgb,var(--accent)_10%,var(--surface-raised))]",
                )}
                id={`${id}-option-${index}`}
                onClick={() => choose(option)}
                onMouseEnter={() => setActive(index)}
                role="option"
              >
                <span className="grid h-5 place-items-center">
                  {chosen && <Check aria-hidden="true" className="text-accent" size={14} />}
                </span>
                <span className="grid min-w-0 gap-0.5">
                  <span className="[overflow-wrap:anywhere]">
                    {option.label}
                    {chosen && <span className="sr-only">, current choice</span>}
                  </span>
                  {option.meta && <span className="text-meta text-ink-muted [overflow-wrap:anywhere]">{option.meta}</span>}
                </span>
              </li>
            );
          })}
        </ul>
        {/* Not an option: a message about the search, announced as one. */}
        <p aria-live="polite" className={cx(noMatch ? POPOVER : "sr-only", noMatch && "text-meta text-ink-muted px-3 py-2")} role="status">
          {noMatch ? emptyText : ""}
        </p>
      </span>
    </FieldShell>
  );
}

const POPOVER =
  "border-line bg-surface-raised shadow-elev-2 absolute top-full left-0 z-[var(--z-top)] m-0 mt-1" +
  " w-[max(100%,18rem)] max-w-[calc(100vw-2rem)] rounded-md border border-solid";
