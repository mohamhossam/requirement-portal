import { TRANSITION } from "../../components/ui/recipes";

/**
 * The field recipe for the worklist's compact controls (docs/design-system.md
 * §11): 36px, a 1px `--line-strong` boundary, `--radius-sm`. Unlike the `Input`
 * and `Select` primitives it does not set `w-full` — these sit in a row and
 * size to their content — and it carries no visible label of its own, because
 * each control says what it is by what it shows. Every one is still labelled.
 */
const FRAME =
  "min-h-9 rounded-sm border border-solid border-line-strong bg-surface px-3 text-body text-ink" +
  ` hover:border-ink-muted focus-visible:border-accent ${TRANSITION}`;

export const CONTROL = `${FRAME} py-2`;

/**
 * A search box: the same 36px frame, drawn by the label around a borderless
 * input. It used to take CONTROL and try to cancel its padding with `py-0`,
 * which lost to `py-2` on utility order, so the box rendered 54px tall beside
 * 36px controls. No vertical padding here at all; the input is 2px shorter than
 * the frame so the 1px border fits inside it. The input draws no outline of its
 * own, so the frame carries the ring while the input has keyboard focus.
 */
export const SEARCH_FRAME =
  `${FRAME} flex min-w-[14rem] max-w-[26rem] flex-1 cursor-text items-center gap-2` +
  " has-[:focus-visible]:border-accent has-[:focus-visible]:[outline:3px_solid_var(--focus)] has-[:focus-visible]:[outline-offset:2px]";
export const SEARCH_INPUT =
  "text-body text-ink min-h-8 min-w-0 flex-1 border-0 bg-transparent p-0 outline-none placeholder:text-ink-muted";
