import type { ReactNode } from "react";

import { cx } from "../../components/ui";
import { FOCUS_RING, HOVER_GROUND, TRANSITION } from "../../components/ui/recipes";

export type Segment<T extends string> = {
  value: T;
  label: ReactNode;
  /** The accessible name, when the visible label is more than one phrase. */
  name?: string;
  icon?: ReactNode;
};

/**
 * A row of mutually exclusive toggles on a sunken track: which version the
 * workbench shows, and which view of it. The pressed one is the white sheet
 * with a rule line, so the accent stays spent on the next action alone.
 * `aria-pressed` rather than tabs: nothing may be pressed while a step of the
 * change workflow has the workbench.
 */
export function Segmented<T extends string>({
  label,
  value,
  options,
  onChange,
  className,
}: {
  label: string;
  value: T | null;
  options: Segment<T>[];
  onChange: (value: T) => void;
  className?: string;
}) {
  return (
    <div
      role="group"
      aria-label={label}
      className={cx(
        "bg-surface-sunken border-line flex w-full min-w-0 gap-1 rounded-md border border-solid p-1 sm:inline-flex sm:w-auto sm:max-w-full",
        className,
      )}
    >
      {options.map((option) => {
        const pressed = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={pressed}
            aria-label={option.name}
            onClick={() => onChange(option.value)}
            className={cx(
              "text-body inline-flex min-h-8 min-w-0 flex-1 cursor-pointer items-center justify-center gap-2 rounded-sm border border-solid px-2 sm:flex-none sm:px-3",
              pressed
                ? "bg-surface border-line-strong text-ink font-semibold"
                : cx("text-ink-muted hover:text-ink border-transparent bg-transparent", HOVER_GROUND),
              FOCUS_RING,
              TRANSITION,
            )}
          >
            {option.icon && <span className="hidden sm:inline-flex">{option.icon}</span>}
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
