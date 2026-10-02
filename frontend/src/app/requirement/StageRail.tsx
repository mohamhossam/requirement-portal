import { Check } from "lucide-react";
import { useEffect, useRef } from "react";
import { Link } from "react-router-dom";

import { cx } from "../../components/ui/cx";
import { HOVER_GROUND, TRANSITION } from "../../components/ui/recipes";
import type { JourneyStep } from "./journey";

/**
 * Where you are in this Requirement's journey — the signature component
 * (docs/design-system.md §11).
 *
 * Six vertical steps, persistent, on every stage including Backlog. It replaces
 * the horizontal bar that vanished on the Backlog route in favour of a `compact`
 * row in that page's own header, and the `<details>` menu before that — three
 * presentations of one model (`ux-plan.md` §3.3). `adr-0047-persistent-journey-
 * stepper` is superseded: the stepper is a rail, and it has six steps.
 *
 * Every state carries a glyph as well as a colour:
 *   complete  a filled check, and the step name in `--ink`
 *   current   `--accent-wash` ground, 3px `--accent` left edge, `--accent` label
 *   blocked   `--ink-faint` with a hollow ring — navigable, because the
 *             destination explains itself better than a disabled control can,
 *             but never reading as available
 *
 * Two different things are marked, because they come apart: the step the journey
 * is waiting on (`current`) and the step you are looking at (`viewing`). On the
 * Backlog route before confirmation those are Backlog and Clarify respectively,
 * and showing only the first leaves a person unable to tell where they are.
 *
 * `complete` and `blocked` used to live only in a class name, so a screen reader
 * heard five identical links: the check mark was decorative and the muted grey
 * meant nothing without sight of it. Both say what they are inside the link,
 * where they join its accessible name.
 *
 * Mobile first: the rail is a horizontally scrolling row of the same six links,
 * and becomes the column at `lg` — the tier docs/design-system.md §10.2 gives to
 * "the widest multi-pane layouts", which is what a 240px rail beside a workspace
 * is. One markup, one model, two shapes, and it folds with the frame around it
 * rather than a tier earlier.
 */

/** What a status adds to the step's name. `current` is carried by aria-current. */
const STATUS_NOTE: Record<JourneyStep["status"], string> = {
  complete: "completed",
  current: "",
  blocked: "not available yet",
  pending: "",
};

export function StageRail({
  steps,
  viewingPath,
}: {
  steps: JourneyStep[];
  /** The route being shown, when it is one of the journey's own. */
  viewingPath?: string;
}) {
  // A plain Link, not a NavLink: which step you are *viewing* is `viewingPath`,
  // not a route match — `/breakdown/features/x/stories/y` is still the Backlog
  // step — and NavLink would add an `aria-current="page"` of its own on top of
  // the one the list item already carries, so the current step announced twice.
  const viewing = (step: JourneyStep) => step.path === viewingPath;
  const list = useRef<HTMLOListElement>(null);

  /**
   * Below `lg` the steps are a row that scrolls sideways, and it opened at
   * step 1 whatever the page: on the Backlog at 390px, "Step 5 of 6" sat above
   * Source, Clarify and Knowledge, with the step it named off-screen. Bring the
   * step being viewed into the row. A jump, not a scroll animation, so reduced
   * motion needs nothing of its own; and nothing happens once the rail is a
   * column and does not scroll.
   */
  useEffect(() => {
    const row = list.current;
    if (!row || row.scrollWidth <= row.clientWidth) return;
    const target = row.querySelector<HTMLElement>('[aria-current="page"]') ?? row.querySelector<HTMLElement>('[aria-current="step"]');
    if (!target) return;
    row.scrollLeft += target.getBoundingClientRect().left - row.getBoundingClientRect().left - 16;
  }, [viewingPath]);
  // "page" is the factual one when you are on it; "step" marks what is owed.
  const marker = (step: JourneyStep) =>
    viewing(step) ? ("page" as const) : step.status === "current" ? ("step" as const) : undefined;

  /**
   * The label with its status appended, as one string. A visually-hidden span
   * beside the label would depend on the name computation putting a space
   * between two inline nodes, which it does not reliably. The visible label
   * stays the start of the name, so speech input still matches what is on screen
   * (WCAG 2.5.3).
   */
  const name = (step: JourneyStep) =>
    STATUS_NOTE[step.status] ? `${step.label} — ${STATUS_NOTE[step.status]}` : undefined;

  /** Where the journey is, for the folded rail. The step being viewed wins over
   *  the step the journey is waiting on: it is the one the person is reading. */
  const marked = steps.findIndex((step) => viewing(step));
  const current = marked >= 0 ? marked : steps.findIndex((step) => step.status === "current");
  const position = current >= 0 ? { index: current + 1, total: steps.length } : null;

  return (
    // `min-w-0`: the scrolling row is inside a grid item, whose default
    // `min-width: auto` would let its content set the track width — which is a
    // 790px page inside a 660px viewport rather than a row that scrolls.
    <nav className="stage-rail min-w-0" aria-label="Requirement workflow">
      {/* Below `lg` the six steps scroll sideways and only three fit, and they
          happen to end flush with the edge — so a fade has nothing partial to
          reveal and the row simply looks finished at three. A count is the
          affordance that survives that: it says how many there are without
          depending on a sliver of the fourth surviving the clip. Hidden once
          the rail is a column and all six are visible at once. */}
      {position && (
        <p className="text-meta text-ink-muted m-0 mb-2 tabular-nums lg:hidden">
          Step {position.index} of {position.total}
        </p>
      )}
      <ol ref={list} className="stage-rail-steps m-0 flex list-none gap-1 overflow-x-auto p-0 lg:grid lg:overflow-visible">
        {steps.map((step, index) => (
          <li
            key={step.key}
            className={cx(
              "min-w-0 shrink-0 lg:shrink",
              step.status === "current" && "current",
              step.status !== "current" && step.status,
              viewing(step) && "viewing",
            )}
            aria-current={marker(step)}
          >
            <Link
              to={step.path}
              aria-label={name(step)}
              className={cx(
                // `border-0` before the left edge: preflight is not imported, so
                // `border-solid` alone leaves the other three sides at the UA's
                // `medium` width in `currentColor` — a box around every step.
                "text-body flex min-h-11 items-center gap-2 whitespace-nowrap rounded-sm border-0 border-l-[3px] border-solid px-3 no-underline lg:whitespace-normal",
                TRANSITION,
                step.status === "current"
                  ? "border-l-[var(--accent)] bg-accent-wash text-accent font-semibold"
                  : step.status === "blocked"
                    ? cx("text-ink-faint border-l-transparent", HOVER_GROUND)
                    : cx("text-ink border-l-transparent", HOVER_GROUND),
                // An underline alone left the step you are viewing unmarked
                // beside the accent-washed step the journey is waiting on —
                // two different languages for "you are here". A sunken
                // ground marks it in the same one without spending the
                // accent a second time.
                viewing(step) && step.status !== "current" &&
                  "font-semibold [box-shadow:inset_0_0_0_1px_var(--line-strong)]",
              )}
            >
              {/* The marker, never colour alone: a check when the step is done,
                  a hollow ring when it cannot help yet, the ordinal otherwise.
                  The number is a visual aid — the list already carries order,
                  and announcing "2 Clarify" only adds a digit to read past. */}
              <span
                className={cx(
                  "text-meta grid size-6 shrink-0 place-items-center rounded-full font-semibold tabular-nums",
                  step.status === "complete" && "bg-success-wash text-success",
                  step.status === "current" && "bg-surface text-accent",
                  step.status === "blocked" &&
                    "text-ink-faint bg-transparent [box-shadow:inset_0_0_0_1px_currentColor]",
                  step.status === "pending" && "bg-surface-sunken text-ink-muted",
                )}
                aria-hidden="true"
              >
                {step.status === "complete" ? <Check size={14} aria-hidden="true" /> : index + 1}
              </span>
              {/* `min-w-0`: a flex child floors at its content width, so without
                  it `truncate` never truncates — it widens the row instead. */}
              <span className="min-w-0 truncate">{step.label}</span>
            </Link>
          </li>
        ))}
      </ol>
    </nav>
  );
}
