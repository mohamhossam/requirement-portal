import { X } from "lucide-react";
import { useId, type ReactNode } from "react";

import { Modal } from "./Modal";
import { Button } from "./ui/Button";

/**
 * The always-available panels — Source, People, the Backlog navigator — on every
 * stage and at every width (docs/ux-plan.md §4).
 *
 * It takes the Modal's `drawer` variant rather than the old `.workspace-drawer`
 * stylesheet, which carried its own font stack, its own near-black and a white
 * ground from a retired visual generation. The chrome now comes from
 * docs/design-system.md §8: `--surface-raised`, a 1px `--line` border, `--elev-3`,
 * and `--scrim` behind it. Focus is trapped, Escape closes, and focus returns to
 * the button that opened it.
 *
 * `portal` keeps it a child of `document.body`, where no ancestor descendant
 * selector can restyle its buttons — which is also what lets a confirmation
 * raised from inside it stay a descendant of the drawer.
 */
export function WorkspaceDrawer({ title, children, onClose }: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  const titleId = useId();
  return (
    <Modal className="workspace-drawer" variant="drawer" labelledBy={titleId} onClose={onClose} portal>
      {/* `-top-6`, not `top-0`: a sticky offset is measured from the scroller's
          content box, so `top-0` held the header 24px below the edge its
          negative margin put it at, and it covered the first 8px of the body. */}
      <header className="border-line bg-surface-raised sticky -top-6 -mx-6 -mt-6 mb-4 flex items-center justify-between gap-4 border-0 border-b border-solid px-6 py-3">
        <h2 className="text-headline text-ink m-0" id={titleId}>{title}</h2>
        <Button variant="ghost" size="icon" aria-label="Close" onClick={onClose} autoFocus>
          <X size={18} aria-hidden="true" />
        </Button>
      </header>
      <div className="workspace-drawer-body [overflow-wrap:anywhere] grid gap-4">{children}</div>
    </Modal>
  );
}
