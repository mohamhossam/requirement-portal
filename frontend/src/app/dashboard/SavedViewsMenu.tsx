import { ChevronDown } from "lucide-react";

import type { SavedRequirementView } from "../../api/client";
import { errorMessage } from "../../api/errors";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Button } from "../../components/ui/Button";
import { cx } from "../../components/ui/cx";
import { HOVER_GROUND, TRANSITION } from "../../components/ui/recipes";
import { CONTROL } from "./controls";

/**
 * Saving and renaming a view is not the task you came to the worklist to do, so
 * it sits behind a disclosure rather than above the requirements as a band of
 * five controls.
 *
 * Still a native `<details>`: it opens and closes from the keyboard and pushes
 * nothing else on the page. The trigger reads as a secondary button with a drawn
 * chevron (it was a `▾` character, and a glyph standing in for an icon is one of
 * the system's bans), and the panel is a popover — `--surface-raised`, a border
 * as well as `--elev-2`, `--radius-lg`, at `--z-top`.
 */
export function SavedViewsMenu({
  views,
  selectedViewId,
  onSelectView,
  viewName,
  onViewName,
  onSave,
  onUpdate,
  onDelete,
  saving,
  error,
}: {
  views: SavedRequirementView[];
  selectedViewId: string;
  onSelectView: (id: string) => void;
  viewName: string;
  onViewName: (name: string) => void;
  onSave: () => void;
  onUpdate: () => void;
  onDelete: () => void;
  saving: boolean;
  error: unknown;
}) {
  return (
    /* `relative`, with the panel pinned to this trigger's right edge: the
       toolbar keeps the trigger at the end of its row (ml-auto on the wrapper),
       so a right-anchored 20rem panel always opens inward rather than off the
       left of the screen, which is where it was at 740px. */
    <details className="group relative">
      <summary
        className={cx(
          "border-line-strong text-body text-ink inline-flex min-h-9 cursor-pointer list-none items-center gap-2",
          "rounded-sm border border-solid bg-transparent px-3 font-semibold [&::-webkit-details-marker]:hidden",
          HOVER_GROUND,
          TRANSITION,
        )}
      >
        Views{selectedViewId ? <span className="text-ink-muted font-normal">· {viewName}</span> : null}
        <ChevronDown
          aria-hidden="true"
          className="text-ink-muted shrink-0 transition-transform duration-[var(--motion-fast)] group-open:rotate-180 motion-reduce:transition-none"
          size={16}
        />
      </summary>
      <div className="border-line bg-surface-raised shadow-elev-2 absolute top-full right-0 z-[var(--z-top)] mt-2 grid w-[min(20rem,calc(100vw-2rem))] gap-3 rounded-lg border border-solid p-4">
        <label className="grid gap-2">
          <span className="text-label text-ink">Saved view</span>
          <select className={cx(CONTROL, "w-full cursor-pointer")} value={selectedViewId} onChange={(event) => onSelectView(event.target.value)}>
            <option value="">Choose a view</option>
            {views.map((view) => <option key={view.id} value={view.id}>{view.name}</option>)}
          </select>
        </label>
        <label className="grid gap-2">
          <span className="text-label text-ink">View name</span>
          <input
            className={cx(CONTROL, "w-full placeholder:text-ink-muted")}
            value={viewName}
            maxLength={80}
            onChange={(event) => onViewName(event.target.value)}
            placeholder="Example: My review queue"
          />
        </label>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="secondary" size="sm" type="button" disabled={!viewName.trim() || saving} onClick={onSave}>
            Save current
          </Button>
          <Button variant="secondary" size="sm" type="button" disabled={!selectedViewId || !viewName.trim() || saving} onClick={onUpdate}>
            Update / rename
          </Button>
          <Button variant="text-danger" disabled={!selectedViewId || saving} onClick={onDelete}>
            Delete
          </Button>
        </div>
        {error ? <ErrorNotice message={errorMessage(error)} /> : null}
      </div>
    </details>
  );
}
