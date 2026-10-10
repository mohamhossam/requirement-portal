import { X } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { useLocation } from "react-router-dom";

import { Modal } from "../Modal";
import { Button } from "../ui/Button";
import { AppSidebar } from "./AppSidebar";
import { AppTopBar } from "./AppTopBar";

/**
 * One frame, on every route (docs/ux-plan.md §4, docs/design-system.md §10.1).
 *
 * It replaces seven page-level shells that each rendered their own header, their
 * own `<main>` and their own width, plus a `breakdown-shell` that changed the
 * font, the button shape and the navigation — §3.3: "Backlog is a different
 * application". Now there is a header, a sidebar and a main column, and a route
 * decides what goes inside main and nothing else.
 *
 * Mobile first, in the literal sense: the base layout is the 375px one — fixed
 * 56px bar, no rail, navigation behind a drawer — and `md` adds the rail beside
 * the content. Nothing is written as a max-width override of a desktop layout.
 *
 * `--nav-width` is the one piece of arithmetic the frame does: the rail's own
 * width, collapsed or not, which main pads itself by at `md` and above. Keeping
 * it in a custom property is what lets one `md:pl-[…]` cover both states without
 * a second class or a second media query.
 */
const COLLAPSE_KEY = "sidebarCollapsed";

/**
 * Persisted per §11 ("collapsible to 56px icons with aria-expanded and persisted
 * state"). Read in a lazy initialiser so the first paint is already correct, and
 * wrapped because Safari's private mode throws on localStorage rather than
 * returning null.
 */
function readCollapsed(): boolean {
  try {
    return localStorage.getItem(COLLAPSE_KEY) === "true";
  } catch {
    return false;
  }
}

export function AppShell({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(readCollapsed);
  const location = useLocation();
  /**
   * The drawer stores the route it was opened on rather than a boolean, so it is
   * open only while you are still on that route.
   *
   * A drawer that survived the navigation it just caused would cover the page it
   * opened, and closing it from an effect on `pathname` means a second render
   * pass every time somebody navigates. This needs neither: a different pathname
   * is simply not the pathname it was opened on. The query string is not part of
   * it, so changing a filter does not close it.
   */
  const [navOpenedAt, setNavOpenedAt] = useState<string | null>(null);
  const navOpen = navOpenedAt === location.pathname;
  const main = useRef<HTMLElement>(null);
  const landedOn = useRef(location.pathname);

  /**
   * A new page takes the focus, so a keyboard or screen-reader user starts at its
   * content rather than on the link they left, or on nothing at all once that link
   * has gone. Focus that is still inside the page stays put: choosing a feature in
   * the breakdown tree changes the address but not the page, and the person is
   * still working in that tree. The query string is not a new page either.
   */
  useEffect(() => {
    if (landedOn.current === location.pathname) return;
    landedOn.current = location.pathname;
    const content = main.current;
    const active = document.activeElement;
    if (!content || (active && active !== document.body && content.contains(active))) return;
    content.focus({ preventScroll: true });
  }, [location.pathname]);

  const toggleCollapsed = useCallback(() => {
    setCollapsed((current) => {
      const next = !current;
      try {
        localStorage.setItem(COLLAPSE_KEY, String(next));
      } catch {
        // A rail that forgets is better than a rail that throws.
      }
      return next;
    });
  }, []);

  return (
    <div
      className="app-frame bg-canvas text-ink min-h-dvh"
      style={{
        "--nav-width": collapsed
          ? "var(--sidebar-width-collapsed)"
          : "var(--sidebar-width)",
      } as React.CSSProperties}
    >
      {/* First focusable thing on the page, and deliberately so: the bar and the
          rail put roughly ten stops between the top of the document and the
          content, on every route, in a tool built for long review sessions. */}
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>

      <AppTopBar onOpenNav={() => setNavOpenedAt(location.pathname)} />

      {/* The rail. `md` and above only: below it, the same nav is the drawer.

          A plain div, not an `<aside>`: the `<nav>` inside is already the
          landmark, and wrapping it in a named complementary landmark put the one
          navigation into the landmark list twice. */}
      <div className="app-sidebar border-line bg-surface-sunken fixed bottom-0 left-0 top-[var(--header-height)] z-[var(--z-chrome)] hidden w-[var(--nav-width)] overflow-y-auto border-0 border-r border-solid p-2 md:block">
        <AppSidebar collapsed={collapsed} onToggleCollapsed={toggleCollapsed} />
      </div>

      {navOpen ? (
        <Modal
          variant="drawer"
          // Left, not right: it belongs to the button that opened it, which is
          // the leftmost control in the bar.
          side="left"
          size="sm"
          label="Navigation"
          onClose={() => setNavOpenedAt(null)}
          portal
        >
          <div className="mb-4 flex items-center justify-between gap-4">
            <p className="text-label text-ink-muted m-0">Sections</p>
            <Button variant="ghost" size="icon" aria-label="Close navigation" onClick={() => setNavOpenedAt(null)}>
              <X size={18} aria-hidden="true" />
            </Button>
          </div>
          <AppSidebar onNavigate={() => setNavOpenedAt(null)} />
        </Modal>
      ) : null}

      {/* `scroll-pt` is WCAG 2.2 2.4.11: the bar is fixed, so anything scrolled
          to by keyboard has to clear it or the focused control lands underneath
          (§10.4). tokens.css sets it on :root for the document scroller; this is
          the same clearance for main's own scroll-into-view. */}
      {/* `tabIndex={-1}`: focusable by the route change above and the skip link, never
          a Tab stop. No outline: it is the page, not a control on it. */}
      <main
        ref={main}
        id="main-content"
        tabIndex={-1}
        className="app-main scroll-pt-[calc(var(--header-height)+var(--space-2))] pt-[var(--header-height)] outline-none md:pl-[var(--nav-width)]"
      >
        {/* Two jobs, two elements. `main` carries the offset that clears the
            fixed chrome; the column inside it carries the measure. Combining
            them would centre the page inside a box that had already been pushed
            right by the rail, which is the same content twice as far from the
            left edge as it should be. */}
        {/* The bottom gutter clears a home indicator as well as the page: on a
            phone in a browser with no bottom chrome, `pb-16` alone puts the last
            control under the indicator. */}
        <div className="mx-auto w-full max-w-[var(--main-max-width)] px-4 pt-6 [padding-bottom:max(var(--space-16),env(safe-area-inset-bottom))] md:px-6 lg:px-10">
          {children}
        </div>
      </main>
    </div>
  );
}
