import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { ConfirmDialog } from "../components/ConfirmDialog";
import { UnsavedChangesContext, interceptableHref, preservesMountedEditors } from "./useUnsavedChanges";

/**
 * Stops unsaved editor content disappearing on navigation. Two ways out of a
 * page are covered:
 *
 *   - leaving the site (reload, close, external link) through `beforeunload`;
 *   - in-app navigation, by intercepting anchor clicks in the capture phase
 *     before React sees them, so a <Link> can be stopped and replayed once the
 *     person confirms.
 *
 * The browser's Back button is NOT covered. Blocking it needs React Router's
 * useBlocker, which requires a data router (createBrowserRouter); this app
 * mounts BrowserRouter, under which useBlocker throws. Migrating is a separate
 * change: when it happens, replace the click listener below with useBlocker and
 * Back is covered too.
 */
export function UnsavedChangesProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const location = useLocation();
  const dirtyKeys = useRef(new Set<string>());
  const [pending, setPending] = useState<string | null>(null);

  // The click listener is installed once, so it reads the current location
  // through a ref kept up to date after each render rather than closing over a
  // stale one.
  const here = useRef("");
  useEffect(() => {
    here.current = location.pathname + location.search;
  }, [location]);

  const register = useCallback((key: string, dirty: boolean) => {
    if (dirty) dirtyKeys.current.add(key);
    else dirtyKeys.current.delete(key);
  }, []);

  useEffect(() => {
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      if (dirtyKeys.current.size === 0) return;
      // Browsers show their own wording; both calls are needed for coverage.
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, []);

  useEffect(() => {
    const onClick = (event: MouseEvent) => {
      if (dirtyKeys.current.size === 0) return;
      const href = interceptableHref(event, here.current);
      if (!href) return;
      // Moving within a workspace that keeps its editors mounted loses nothing.
      if (preservesMountedEditors(here.current, href)) return;
      event.preventDefault();
      event.stopPropagation();
      setPending(href);
    };
    // Capture phase, on document: runs before React's delegated handlers, so
    // stopPropagation keeps the Link's own onClick from firing.
    document.addEventListener("click", onClick, true);
    return () => document.removeEventListener("click", onClick, true);
  }, []);

  const value = useMemo(() => ({ register }), [register]);

  return (
    <UnsavedChangesContext.Provider value={value}>
      {children}
      {pending !== null && (
        <ConfirmDialog
          title="Leave without saving?"
          message="This editor has changes that have not been saved. Leaving now discards them."
          confirmLabel="Discard changes and leave"
          onCancel={() => setPending(null)}
          onConfirm={() => {
            const destination = pending;
            setPending(null);
            // The editors unmount on navigation and deregister themselves, but
            // clearing first keeps a second prompt off the replayed click.
            dirtyKeys.current.clear();
            void navigate(destination);
          }}
        />
      )}
    </UnsavedChangesContext.Provider>
  );
}
