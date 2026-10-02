import { FileText, Menu, Plus } from "lucide-react";
import { Link, useLocation } from "react-router-dom";

import { useAuth } from "../../auth/authContext";
import { NotificationCenter } from "../../features/jobs/NotificationCenter";
import { Button, ButtonLink } from "../ui/Button";
import { CONTROL_BASE } from "../ui/recipes";
import { HelpMenu } from "./HelpMenu";

/**
 * 56px of chrome, and only what docs/ux-plan.md §4 leaves in it: brand,
 * help, notifications, account, primary action.
 *
 * What is *not* here is the point. The header navigation row is gone —
 * `adr-0050-header-navigation-row` is superseded — and so is the `<details>`
 * "Menu" the Backlog route grew in its place. There is one navigation, it is the
 * sidebar, and on this tier it is a drawer this bar opens.
 *
 * The bar drops from 64px to 56px (§10.1): with the stage rail promoted to a
 * persistent vertical element, the old horizontal stepper's height is reclaimed.
 */
export function AppTopBar({ onOpenNav }: { onOpenNav: () => void }) {
  const auth = useAuth();
  const location = useLocation();
  // One primary action, and it is the same one everywhere — except on the screen
  // that already is it.
  const showPrimary = location.pathname !== "/requirements/new";
  return (
    /* The side padding clears a notch: this bar is full-bleed and fixed, and in
       landscape on a notched phone the leftmost control lands under the cutout
       without the inset. */
    <header className="app-topbar border-line bg-surface fixed inset-x-0 top-0 z-[var(--z-chrome)] flex h-[var(--header-height)] items-center gap-2 border-0 border-b border-solid px-3 [padding-left:max(var(--space-3),env(safe-area-inset-left))] [padding-right:max(var(--space-3),env(safe-area-inset-right))] md:px-4">
      <Button
        variant="ghost"
        size="icon"
        className="md:hidden"
        aria-label="Open navigation"
        aria-haspopup="dialog"
        onClick={onOpenNav}
      >
        <Menu size={20} aria-hidden="true" />
      </Button>

      <Link
        to="/"
        className="brand-lockup text-ink flex min-h-6 min-w-0 items-center gap-2 no-underline"
        aria-label="Requirement AI — requirements"
      >
        <FileText className="text-accent shrink-0" size={22} aria-hidden="true" />
        {/* `translate="no"`: a product name put through an auto-translator comes
            back as something nobody can search for or say out loud. `min-w-0` so
            `truncate` has something to shrink against. */}
        {/* Below `sm` the wordmark is hidden rather than squeezed: with five
            controls in a 375px bar `truncate` shrank it to nothing, which reads
            as a rendering fault. The glyph is the brand at that width, and the
            link keeps its accessible name either way. */}
        <strong className="text-title min-w-0 truncate tracking-tight max-sm:sr-only" translate="no">
          Requirement AI
        </strong>
      </Link>

      <div className="ml-auto flex items-center gap-1 md:gap-2">
        {auth?.sessionExpired && (
          <Button variant="secondary" size="sm" onClick={() => void auth.signIn()}>
            Session expired — sign in
          </Button>
        )}
        <HelpMenu />
        {auth?.actor && <NotificationCenter />}
        {auth?.actor && (
          <div className="actor-menu flex items-center gap-2">
            {/* Identity is chrome, and chrome recedes: the name and address are
                the smallest legible register, and below `md` the address goes —
                a 375px bar cannot hold both and the brand. */}
            <span className="text-meta hidden leading-tight sm:grid">
              <strong className="text-ink">{auth.actor.display_name}</strong>
              <small className="text-ink-muted lg:block hidden">{auth.actor.email}</small>
            </span>
            {auth.config?.mode === "fake" ? (
              <label>
                {/* One label, not two. An `aria-label` on the select would
                    override this, so the sr-only text would be announced by
                    nothing and maintained by everyone. */}
                <span className="sr-only">Development persona</span>
                <select
                  className={`${CONTROL_BASE} max-w-[10rem]`}
                  value={auth.actor.id}
                  onChange={(event) => {
                    void auth.switchFakeActor(event.target.value).catch(() => undefined);
                  }}
                >
                  {auth.config.fake_actors.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.display_name}
                    </option>
                  ))}
                </select>
              </label>
            ) : (
              <Button variant="text" onClick={() => void auth.signOut()}>
                Sign out
              </Button>
            )}
          </div>
        )}
        {showPrimary && (
          <ButtonLink
            variant="primary"
            to="/requirements/new"
            className="header-action"
            icon={<Plus size={17} aria-hidden="true" />}
          >
            {/* The act, not the object — and below `sm` the glyph carries it,
                because a five-control bar at 375px has no room for the words. */}
            <span className="max-sm:sr-only">New requirement</span>
          </ButtonLink>
        )}
      </div>
    </header>
  );
}
