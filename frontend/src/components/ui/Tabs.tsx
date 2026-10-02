import { LoaderCircle } from "lucide-react";
import {
  createContext,
  useCallback,
  useContext,
  useId,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from "react";

import { cx } from "./cx";
import { HOVER_GROUND, TRANSITION } from "./recipes";

/**
 * Tabs, built to the WAI-ARIA tabs pattern.
 *
 * There is no tab component in the product today — the screens that want one
 * render every section stacked, which is how `/review` grew thirteen of them
 * (`ux-plan.md` §3.6). So this is written to the pattern rather than to an
 * existing shape:
 *
 *   - one stop in the tab order for the whole set (roving `tabIndex`), so
 *     Tab moves past the tablist rather than through six of them;
 *   - Left/Right, Home and End move between tabs;
 *   - `aria-controls` and `aria-labelledby` tie each tab to its panel;
 *   - the panel is focusable, so Tab from the selected tab lands in the
 *     content it just revealed.
 *
 * Activation is automatic — moving to a tab selects it. That is the pattern's
 * default and the right call when panels are already in memory. A tab whose
 * panel has to be fetched should render the fetch inside the panel, not make
 * the person press Enter to find out.
 */
type TabsApi = {
  value: string;
  select: (value: string) => void;
  baseId: string;
};

const TabsContext = createContext<TabsApi | null>(null);

function useTabs(part: string): TabsApi {
  const api = useContext(TabsContext);
  if (!api) throw new Error(`<${part}> must be rendered inside <Tabs>`);
  return api;
}

export function Tabs({
  value,
  defaultValue,
  onValueChange,
  className,
  children,
}: {
  /** Controlled selection. Leave out and pass `defaultValue` to let this own it. */
  value?: string;
  defaultValue?: string;
  onValueChange?: (value: string) => void;
  className?: string;
  children: ReactNode;
}) {
  const baseId = useId();
  const [uncontrolled, setUncontrolled] = useState(defaultValue ?? "");
  const controlled = value !== undefined;
  const current = controlled ? value : uncontrolled;

  const select = useCallback(
    (next: string) => {
      if (!controlled) setUncontrolled(next);
      onValueChange?.(next);
    },
    [controlled, onValueChange],
  );

  const api = useMemo(() => ({ value: current, select, baseId }), [current, select, baseId]);

  return (
    <TabsContext.Provider value={api}>
      <div className={cx("grid gap-4", className)}>{children}</div>
    </TabsContext.Provider>
  );
}

/**
 * The strip. `--line` under the whole row rather than a box around each tab:
 * the underline is what makes the selected one read as attached to the panel
 * below it, and a row of outlined boxes is a row of buttons.
 */
export function TabList({
  label,
  className,
  children,
}: {
  /** Names the set — "Requirement sections", not "Tabs". */
  label: string;
  className?: string;
  children: ReactNode;
}) {
  const list = useRef<HTMLDivElement>(null);

  const move = (event: KeyboardEvent<HTMLDivElement>) => {
    const keys = ["ArrowLeft", "ArrowRight", "Home", "End"];
    if (!keys.includes(event.key)) return;
    const tabs = [...(list.current?.querySelectorAll<HTMLButtonElement>('[role="tab"]') ?? [])]
      .filter((tab) => tab.getAttribute("aria-disabled") !== "true");
    if (tabs.length === 0) return;
    const at = tabs.findIndex((tab) => tab === document.activeElement);
    const next =
      event.key === "Home"
        ? 0
        : event.key === "End"
          ? tabs.length - 1
          : // Wraps, which is what the pattern asks for: from the last tab,
            // Right returns to the first rather than dead-ending.
            (at + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
    event.preventDefault();
    // Automatic activation: focus moves and `onFocus` on the tab selects it.
    tabs[next]?.focus();
  };

  return (
    <div
      aria-label={label}
      className={cx(
        "flex flex-wrap items-end gap-1 [border-bottom:1px_solid_var(--line)]",
        className,
      )}
      onKeyDown={move}
      ref={list}
      role="tablist"
    >
      {children}
    </div>
  );
}

export function Tab({
  value,
  icon,
  count,
  loading = false,
  disabled = false,
  className,
  children,
}: {
  value: string;
  icon?: ReactNode;
  /** A count beside the label. Only render one when it is non-zero and it matters. */
  count?: number;
  /** This tab's panel is fetching. Shows the ring and sets `aria-busy`. */
  loading?: boolean;
  disabled?: boolean;
  className?: string;
  children: ReactNode;
}) {
  const { value: selected, select, baseId } = useTabs("Tab");
  const active = selected === value;

  return (
    <button
      aria-busy={loading || undefined}
      aria-controls={`${baseId}-panel-${value}`}
      aria-disabled={disabled || undefined}
      aria-selected={active}
      className={cx(
        // 36px, on the control ladder, and a 2px underline rather than a
        // border switch — a border that only appears when selected shifts
        // every other tab by 2px as you move along the row.
        "text-body relative -mb-px inline-flex min-h-9 cursor-pointer items-center gap-2",
        "border-0 border-b-2 border-solid bg-transparent px-3 py-2 font-semibold",
        active
          ? "border-b-accent text-accent"
          : cx("text-ink-muted hover:text-ink border-b-transparent", !disabled && HOVER_GROUND),
        disabled && "text-ink-faint cursor-not-allowed hover:text-ink-faint",
        TRANSITION,
        className,
      )}
      id={`${baseId}-tab-${value}`}
      // `aria-disabled`, not `disabled`. A disabled button is removed from the
      // accessibility tree's reach entirely, so a person tabbing through never
      // learns the tab exists — and the point of showing an unavailable tab is
      // that the set is complete. Activation is refused here instead.
      // Roving: only the selected tab is in the tab order.
      onClick={() => {
        if (!disabled) select(value);
      }}
      onFocus={() => {
        if (!disabled) select(value);
      }}
      role="tab"
      tabIndex={active ? 0 : -1}
      type="button"
    >
      {loading ? (
        <LoaderCircle
          aria-hidden="true"
          className="animate-spin motion-reduce:animate-none"
          size={14}
        />
      ) : (
        icon
      )}
      {children}
      {count !== undefined && (
        <span
          className={cx(
            "text-label rounded-full px-1.5 py-0.5 tabular-nums",
            active ? "bg-accent text-on-accent" : "bg-surface-sunken text-ink-muted",
          )}
        >
          {count}
        </span>
      )}
    </button>
  );
}

export function TabPanel({
  value,
  className,
  children,
}: {
  value: string;
  className?: string;
  children: ReactNode;
}) {
  const { value: selected, baseId } = useTabs("TabPanel");
  // Unmounted rather than hidden: a hidden panel still holds focusable
  // controls that Tab reaches and nothing announces.
  if (selected !== value) return null;

  return (
    <div
      aria-labelledby={`${baseId}-tab-${value}`}
      className={cx("focus-visible:[outline:3px_solid_var(--focus)] focus-visible:[outline-offset:2px]", className)}
      id={`${baseId}-panel-${value}`}
      role="tabpanel"
      // The panel takes focus itself so Tab from the selected tab lands in the
      // content it just revealed rather than skipping past it.
      tabIndex={0}
    >
      {children}
    </div>
  );
}
