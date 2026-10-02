import { Boxes, UsersRound } from "lucide-react";
import { NavLink } from "react-router-dom";

import { cx } from "../../components/ui";
import { FOCUS_RING, TRANSITION } from "../../components/ui/recipes";

const LINKS = [
  { to: "/architecture-knowledge", label: "Architecture catalogue", icon: Boxes, end: true },
  { to: "/architecture-knowledge/squads", label: "Squad catalogue", icon: UsersRound, end: false },
];

/**
 * The two catalogues live under Documents (no new top-level destination,
 * ux-plan §4); this row moves between them and says which one is open.
 */
export function CatalogueNav() {
  return (
    <nav aria-label="Catalogues" className="border-line mb-6 flex flex-wrap gap-1 border-0 border-b border-solid">
      {LINKS.map(({ to, label, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          className={({ isActive }) => cx(
            "text-body -mb-px inline-flex min-h-11 items-center gap-2 border-0 border-b-2 border-solid px-3 no-underline",
            isActive ? "border-b-accent text-ink font-semibold" : "text-ink-muted hover:text-ink border-b-transparent",
            FOCUS_RING,
            TRANSITION,
          )}
        >
          <Icon aria-hidden="true" size={16} className="hidden sm:block" />
          {label}
        </NavLink>
      ))}
    </nav>
  );
}
