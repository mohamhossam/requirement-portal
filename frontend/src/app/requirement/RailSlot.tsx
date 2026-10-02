import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

/**
 * Lets a stage render its own navigation into the requirement's rail column.
 *
 * The Backlog is the only stage with depth inside it — Epic → Feature → Story —
 * and docs/ux-plan.md §4 calls that "legitimate depth *within* a step, not a
 * second navigation system". It used to be a third column anyway, which at `lg`
 * meant 240px of global sidebar plus 240px of stage rail plus 280px of tree
 * before the item being reviewed got anything; 02-breakdown-workspace.css said
 * so itself and deferred the fix ("that is Phase 4's call, not this pass's").
 * This is Phase 4, and the tree now unfolds beneath the Backlog step in the rail
 * it belongs to.
 *
 * A portal rather than props, for one reason: the tree's data is read by
 * `BreakdownView` on the Backlog stage only, and lifting it into
 * `RequirementWorkspaceShell` would make every stage fetch the backlog to render
 * a rail. That is a data-flow change, and this redesign is presentation only
 * (CLAUDE.md). The portal moves where the tree *renders* and leaves where it is
 * *fetched* untouched. `WorkspaceDrawer` already reaches for the same mechanism.
 */
const RailSlotContext = createContext<{
  node: HTMLElement | null;
  attach: (node: HTMLElement | null) => void;
}>({ node: null, attach: () => {} });

export function RailSlotProvider({ children }: { children: ReactNode }) {
  // `useState` rather than `useRef` on purpose: a ref's mutation does not
  // re-render, so the consumer would read `null` on the first pass and never
  // hear that the target had arrived.
  const [node, setNode] = useState<HTMLElement | null>(null);
  // Memoised, because an inline object literal here is a new value on every
  // render of the requirement shell, and every consumer of this context would
  // re-render for it even though the outlet node had not moved. `setNode` is
  // already referentially stable, so `node` is the only real dependency.
  const value = useMemo(() => ({ node, attach: setNode }), [node]);
  return <RailSlotContext.Provider value={value}>{children}</RailSlotContext.Provider>;
}

/** Where the stage's own navigation lands, directly under the journey steps. */
export function RailSlotOutlet({ className }: { className?: string }) {
  const { attach } = useContext(RailSlotContext);
  return <div className={className} ref={attach} />;
}

/** Renders `children` into the outlet. Nothing at all until the outlet mounts. */
export function RailSlot({ children }: { children: ReactNode }) {
  const { node } = useContext(RailSlotContext);
  return node ? createPortal(children, node) : null;
}
