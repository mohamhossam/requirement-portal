import { ArrowDown, ArrowUp, ChevronsUpDown, TriangleAlert } from "lucide-react";
import type { HTMLAttributes, ReactNode, TdHTMLAttributes, ThHTMLAttributes } from "react";

import { Skeleton } from "../Skeleton";
import { cx } from "./cx";
import { HOVER_GROUND_SOFT, TRANSITION } from "./recipes";

/**
 * The table (§11): sticky header on `--surface-sunken`, 44px rows, `--line`
 * dividers, hover as a tone shift, and column headers that are real sort
 * buttons exposing `aria-sort` — `ux-plan.md` §3.12 records that the product
 * has only ever had a sort dropdown.
 *
 * Composed rather than configured. A `columns={[…]}` table has to grow a prop
 * for every cell anyone ever wants to render differently, and the screens here
 * stack two values in a cell, badge one of them and right-align a third. So
 * these are the parts, and the screen writes the markup.
 */
export function Table({
  caption,
  captionVisible = false,
  framed = true,
  className,
  children,
  ...rest
}: HTMLAttributes<HTMLTableElement> & {
  /** What this table lists. Required — a table with no name is a grid of words. */
  caption: ReactNode;
  captionVisible?: boolean;
  /**
   * The frame's own border, radius and ground. Off when the table sits inside a
   * panel that already draws them — a worklist under its toolbar — so the page
   * does not show two borders one pixel apart.
   */
  framed?: boolean;
}) {
  return (
    // The frame owns the radius and the border so the sticky header can sit
    // flush against the top edge without rounding its own corners.
    //
    // It is also a scroll container, which is why it is a labelled, focusable
    // region rather than a plain div: a container that scrolls and cannot be
    // focused can only be scrolled by dragging it, so on a table wider than the
    // column there are cells a keyboard never reaches (WCAG 2.1.1). `tabIndex`
    // puts it in the tab order so the arrow keys apply; `role="region"` gives
    // that stop a name, because a nameless group announces as "group" and tells
    // a person nothing about what they have just landed in. The caption names
    // both the table and the region, so there is one string to keep true.
    <div
      aria-label={typeof caption === "string" ? caption : undefined}
      className={cx(
        "overflow-x-auto",
        framed && "border-line bg-surface rounded-md border border-solid",
        "focus-visible:[outline:3px_solid_var(--focus)] focus-visible:[outline-offset:2px]",
      )}
      role="region"
      tabIndex={0}
    >
      <table {...rest} className={cx("w-full border-collapse text-left", className)}>
        <caption
          className={cx(
            captionVisible
              ? "text-ink-muted text-meta [border-bottom:1px_solid_var(--line)] px-3 py-2 text-left"
              : "sr-only",
          )}
        >
          {caption}
        </caption>
        {children}
      </table>
    </div>
  );
}

/**
 * Sticky by default, at `--z-sticky`. It stays inside the scroll container the
 * frame above creates, so it pins to the top of the table rather than to the
 * viewport — the fixed app header is at `--z-chrome`, above this, and covering
 * a focused row with it would fail WCAG 2.2 2.4.11 (§10.4).
 */
export function TableHead({
  sticky = true,
  className,
  children,
  ...rest
}: HTMLAttributes<HTMLTableSectionElement> & { sticky?: boolean }) {
  return (
    <thead
      {...rest}
      className={cx(
        // A directional border is written as one arbitrary property, never as
        // `border-b border-solid`. Tailwind's preflight is deliberately not
        // imported (src/styles/index.css), so `border-solid` sets a style on
        // all four sides while `border-b` sets a width on one — and the other
        // three then fall back to the initial width, `medium`, which is 3px.
        // That renders a 3px box where a 1px rule was asked for.
        "bg-surface-sunken [border-bottom:1px_solid_var(--line)]",
        sticky && "sticky top-0 z-[var(--z-sticky)]",
        className,
      )}
    >
      {children}
    </thead>
  );
}

export type SortDirection = "asc" | "desc";

// `align` is omitted, not extended: the deprecated HTML attribute of that name
// is typed "left" | "center" | "right" | …, and intersecting it with the logical
// values below resolves to `never`.
export type TableHeaderCellProps = Omit<
  ThHTMLAttributes<HTMLTableCellElement>,
  "onClick" | "align"
> & {
  /**
   * Current direction, or null when this column is not the sort. Omit `onSort`
   * entirely for a column that cannot be sorted — a header that looks like a
   * button and does nothing is worse than a plain one.
   */
  sort?: SortDirection | null;
  onSort?: () => void;
  align?: "start" | "end";
};

/**
 * A column header. With `onSort` it becomes a button inside the `<th>`, and the
 * `<th>` carries `aria-sort` — the attribute belongs on the cell, not on the
 * control inside it.
 */
export function TableHeaderCell({
  sort = null,
  onSort,
  align = "start",
  className,
  children,
  ...rest
}: TableHeaderCellProps) {
  const label = cx("text-label text-ink-muted", align === "end" && "text-right");

  if (!onSort) {
    return (
      <th {...rest} className={cx(label, "px-3 py-2", className)} scope="col">
        {children}
      </th>
    );
  }

  const Icon = sort === "asc" ? ArrowUp : sort === "desc" ? ArrowDown : ChevronsUpDown;

  return (
    <th
      {...rest}
      aria-sort={sort === "asc" ? "ascending" : sort === "desc" ? "descending" : "none"}
      className={cx(label, "p-0", className)}
      scope="col"
    >
      <button
        className={cx(
          "text-label text-ink-muted hover:text-ink flex min-h-9 w-full cursor-pointer items-center gap-1.5",
          "border-0 bg-transparent px-3 py-2",
          align === "end" && "justify-end",
          HOVER_GROUND_SOFT,
          TRANSITION,
        )}
        onClick={onSort}
        type="button"
      >
        {children}
        {/* Direction is carried by aria-sort for assistive technology and by the
            glyph for everyone else; the muted double chevron on an unsorted
            column is what says the column can be sorted at all. */}
        <Icon
          aria-hidden="true"
          className={cx("shrink-0", sort ? "text-accent" : "text-ink-faint")}
          size={14}
        />
      </button>
    </th>
  );
}

/**
 * The rows, and the three states that replace them.
 *
 * They live here rather than around the whole table on purpose: the header
 * stays put while the body swaps, so the columns do not jump when fifteen rows
 * arrive, which is the no-content-jumping rule (§9).
 */
export function TableBody({
  columns,
  loading = false,
  loadingLabel = "Loading rows…",
  error,
  empty,
  className,
  children,
  ...rest
}: HTMLAttributes<HTMLTableSectionElement> & {
  /** How many columns the loading, error and empty rows should span. */
  columns: number;
  loading?: boolean;
  loadingLabel?: string;
  /** Rendered instead of the rows, and announced assertively. */
  error?: ReactNode;
  /** Rendered when there is nothing to show and nothing went wrong. */
  empty?: ReactNode;
}) {
  let state: ReactNode = null;
  if (loading) {
    state = <Skeleton label={loadingLabel} variant="row" />;
  } else if (error) {
    state = (
      <span className="text-danger text-body flex items-center gap-2 font-semibold">
        <TriangleAlert aria-hidden="true" size={16} />
        {error}
      </span>
    );
  } else if (empty) {
    state = <span className="text-ink-muted text-body">{empty}</span>;
  }

  return (
    // The dividers sit between rows rather than under every one, so the last
    // row has no rule of its own butting against the frame. `divide-y` is not
    // used: it sets a width and leaves the style at `none` without preflight,
    // so the rules never paint at all.
    <tbody
      {...rest}
      className={cx("[&>tr+tr]:[border-top:1px_solid_var(--line)]", className)}
    >
      {state === null ? (
        children
      ) : (
        <tr>
          <td className="px-3 py-6" colSpan={columns} role={error ? "alert" : undefined}>
            {state}
          </td>
        </tr>
      )}
    </tbody>
  );
}

/**
 * `interactive` is presentation only — hover tone and a pointer cursor. It does
 * not make the row clickable, and deliberately so: a `<tr>` with an onClick is
 * unreachable by keyboard, and giving it a tabindex produces a focusable thing
 * with no role saying what activating it would do. Put a real `<a>` or
 * `<button>` in the first cell and let the row styling follow it.
 */
export function TableRow({
  interactive = false,
  selected = false,
  className,
  children,
  ...rest
}: HTMLAttributes<HTMLTableRowElement> & { interactive?: boolean; selected?: boolean }) {
  return (
    <tr
      {...rest}
      aria-selected={selected || undefined}
      className={cx(
        "h-11",
        interactive && cx("cursor-pointer", HOVER_GROUND_SOFT, TRANSITION),
        // Selection carries a left edge as well as a ground, because the wash
        // is nearly invisible in the dark theme (§4.5).
        selected && "bg-accent-wash shadow-[inset_3px_0_0_var(--accent)]",
        className,
      )}
    >
      {children}
    </tr>
  );
}

export function TableCell({
  numeric = false,
  className,
  children,
  ...rest
}: TdHTMLAttributes<HTMLTableCellElement> & {
  /** Right-aligned and lining figures, so a column of numbers compares down. */
  numeric?: boolean;
}) {
  return (
    <td
      {...rest}
      className={cx(
        "text-body text-ink-soft px-3 py-2 align-middle",
        numeric && "text-right tabular-nums",
        className,
      )}
    >
      {children}
    </td>
  );
}

/**
 * The bulk-action bar (§11). It replaces the toolbar *in place* rather than
 * floating over the rows: a bar that hovers covers the content a person is
 * deciding about, and on a short list it can cover the whole thing.
 */
export function TableBulkBar({
  count,
  noun = "item",
  className,
  children,
}: {
  count: number;
  /** Singular. Pluralised here, so no screen ever renders "1 items". */
  noun?: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div
      className={cx(
        "border-line bg-accent-wash border-l-accent flex flex-wrap items-center gap-3",
        "rounded-md border border-solid border-l-[3px] px-3 py-2",
        className,
      )}
      role="status"
    >
      <strong className="text-body text-ink tabular-nums">
        {new Intl.NumberFormat().format(count)} {noun}
        {count === 1 ? "" : "s"} selected
      </strong>
      <span className="ml-auto flex flex-wrap items-center gap-2">{children}</span>
    </div>
  );
}
