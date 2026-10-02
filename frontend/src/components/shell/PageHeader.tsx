import type { ReactNode } from "react";

/**
 * The one page title in the app.
 *
 * docs/ux-plan.md §3.4 counted five labels stacked above the first question on
 * `/clarify`: a header context line, an eyebrow, the stage `h1`, a panel eyebrow
 * and an `h2` — with the requirement's own title, the thing a person with four
 * tabs open is actually looking for, buried inside the eyebrow. So: one `h1`,
 * one supporting line, and whatever the page genuinely acts on.
 *
 * `eyebrow` exists for the pages whose title needs a register above it — a
 * catalogue, a portfolio view — and not for restating where you are. The rail
 * already says that.
 *
 * Mobile first: the actions sit under the heading and stretch, and only take the
 * end of the title row once there is width for them.
 */
export function PageHeader({
  title,
  description,
  eyebrow,
  actions,
  children,
}: {
  title: ReactNode;
  description?: ReactNode;
  eyebrow?: ReactNode;
  /** What this page does. Kept to the primary act plus its alternatives. */
  actions?: ReactNode;
  /** Anything belonging to the header but not to the title — a filter row. */
  children?: ReactNode;
}) {
  return (
    <header className="page-head border-line mb-6 grid gap-3 border-0 border-b border-solid pb-4">
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
        <div className="grid min-w-0 gap-1">
          {eyebrow ? <p className="text-label text-ink-muted m-0">{eyebrow}</p> : null}
          {/* `text-balance` so a two-line requirement title does not leave one
              word on the second line; `break-words` because some of them are one
              long unspaced system name. */}
          <h1 className="text-display text-ink m-0 text-balance break-words">{title}</h1>
          {description ? (
            <p className="text-ink-muted text-body m-0 max-w-[80ch] text-pretty">{description}</p>
          ) : null}
        </div>
        {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
      </div>
      {children}
    </header>
  );
}
