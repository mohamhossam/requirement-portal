import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { NavLink } from "react-router-dom";

import { cx } from "../ui/cx";
import { FOCUS_RING, HOVER_GROUND, TRANSITION } from "../ui/recipes";
import { DESTINATIONS } from "./navigation";

/**
 * The only global navigation in the product (docs/design-system.md §11).
 *
 * 240px, `--surface-sunken`, a `--line` right edge, four destinations,
 * collapsible to 56px of icons with `aria-expanded` and persisted state. The
 * active item takes an `--accent-wash` ground and a 3px `--accent` left edge —
 * the same "this one" mark the stage rail uses.
 *
 * One component, two presentations, and the *markup* is identical in both: at
 * `md` and above it is the fixed rail; below it is the content of the drawer
 * `AppShell` opens from the header. That is the point of §3.1 — the same list in
 * the same order, whatever the width and whatever the route.
 */
export function AppSidebar({
  collapsed = false,
  onToggleCollapsed,
  onNavigate,
}: {
  /** Icons only. Ignored inside the mobile drawer, which always has the room. */
  collapsed?: boolean;
  /** Absent inside the drawer: collapsing is a desktop affordance. */
  onToggleCollapsed?: () => void;
  /** Called after a destination is chosen, so the drawer can close itself. */
  onNavigate?: () => void;
}) {
  return (
    <nav
      className="app-nav grid content-start gap-1"
      aria-label="Global"
      data-collapsed={collapsed ? "true" : "false"}
    >
      {DESTINATIONS.map(({ to, label, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          onClick={onNavigate}
          // 44px rather than the 36px control floor: this is the one list a
          // person hits with a thumb, and §6 calls its sizes floors.
          className={({ isActive }) =>
            cx(
              // `border-0` first, and it is not redundant: Tailwind's preflight
              // is deliberately not imported (styles/index.css), so `border-solid`
              // on its own leaves the other three sides at the UA's `medium`
              // width in `currentColor` — a black box around every nav item.
              "text-body flex min-h-11 items-center gap-3 rounded-sm border-0 border-l-[3px] border-solid px-3 no-underline",
              collapsed && "justify-center px-0",
              TRANSITION,
              isActive
                ? "border-l-[var(--accent)] bg-accent-wash text-accent font-semibold"
                : cx("border-l-transparent text-ink font-normal", HOVER_GROUND),
            )
          }
          // The label is the accessible name in both presentations; collapsed,
          // the visible text is gone but the name must not be.
          aria-label={collapsed ? label : undefined}
          title={collapsed ? label : undefined}
        >
          <Icon size={18} aria-hidden="true" />
          <span className={collapsed ? "sr-only" : undefined}>{label}</span>
        </NavLink>
      ))}

      {onToggleCollapsed ? (
        <button
          type="button"
          onClick={onToggleCollapsed}
          aria-expanded={!collapsed}
          className={cx(
            "text-meta text-ink-muted mt-2 hidden min-h-11 cursor-pointer items-center gap-3 rounded-sm border-0 bg-transparent px-3 md:flex",
            collapsed && "justify-center px-0",
            TRANSITION,
            FOCUS_RING,
            "hover:text-ink",
          )}
        >
          {collapsed ? (
            <PanelLeftOpen size={18} aria-hidden="true" />
          ) : (
            <PanelLeftClose size={18} aria-hidden="true" />
          )}
          <span className={collapsed ? "sr-only" : undefined}>
            {collapsed ? "Expand navigation" : "Collapse navigation"}
          </span>
        </button>
      ) : null}
    </nav>
  );
}
