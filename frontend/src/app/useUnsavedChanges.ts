import { createContext, useContext, useEffect, useId, useState } from "react";

/**
 * Registry for editors whose content would be lost on navigation.
 *
 * Editors register their dirty state here; UnsavedChangesProvider owns the
 * interception, so a workspace with several mounted editors still prompts once.
 */
export type UnsavedChangesRegistry = { register: (key: string, dirty: boolean) => void };

export const UnsavedChangesContext = createContext<UnsavedChangesRegistry | null>(null);

/**
 * Registers this component as holding unsaved work while `dirty` is true.
 * Outside a provider this is a no-op, so components stay renderable on their own.
 */
export function useUnsavedChanges(dirty: boolean) {
  const registry = useContext(UnsavedChangesContext);
  const key = useId();
  useEffect(() => {
    if (!registry) return;
    registry.register(key, dirty);
    return () => registry.register(key, false);
  }, [registry, key, dirty]);
}

/**
 * True once `value` differs from what it was when the editor opened. The
 * baseline is captured on first render, so re-opening an editor resets it.
 */
export function useIsDirty(value: unknown): boolean {
  const current = JSON.stringify(value);
  const [baseline] = useState(current);
  return baseline !== current;
}

/** Captures a baseline and registers the guard in one call. Returns dirtiness. */
export function useUnsavedGuard(value: unknown, enabled = true): boolean {
  const dirty = useIsDirty(value);
  useUnsavedChanges(enabled && dirty);
  return dirty;
}

/**
 * An ordinary left-click on an in-app link that would leave the current page.
 * `here` is the router's location rather than window.location, so the check is
 * correct under any router the app or its tests mount.
 */
export function interceptableHref(event: MouseEvent, here: string): string | null {
  if (event.defaultPrevented || event.button !== 0) return null;
  if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return null;

  const anchor = (event.target as Element | null)?.closest?.("a[href]");
  if (!(anchor instanceof HTMLAnchorElement)) return null;
  if (anchor.hasAttribute("download")) return null;
  if (anchor.target && anchor.target !== "_self") return null;

  const target = new URL(anchor.href, window.location.href);
  if (target.origin !== window.location.origin) return null;
  // A fragment jump within the current page loses nothing.
  if (target.pathname + target.search === here) return null;

  return target.pathname + target.search + target.hash;
}

/**
 * Navigation that keeps the open editors mounted, so nothing is actually lost.
 *
 * ADR-0045 keeps keyed artifact editors mounted across the focused Breakdown
 * workspace, hiding unselected detail rather than unmounting it, precisely so
 * that unsaved drafts survive moving between backlog items. Warning about a
 * loss that does not happen trains people to dismiss the warning that matters.
 *
 * This is a route rule rather than something each editor declares, because the
 * knowledge is about which routes share a mounted workspace, not about any one
 * editor. A second zone of mounted editors would mean generalising it.
 */
const BREAKDOWN_WORKSPACE = /^\/requirements\/([^/]+)\/breakdown(?:[/?#]|$)/;

export function preservesMountedEditors(from: string, to: string): boolean {
  const origin = BREAKDOWN_WORKSPACE.exec(from);
  const destination = BREAKDOWN_WORKSPACE.exec(to);
  // Same requirement, both inside its Breakdown workspace: it stays mounted.
  return Boolean(origin && destination && origin[1] === destination[1]);
}
