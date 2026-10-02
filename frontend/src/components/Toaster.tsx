import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Link } from "react-router-dom";
import { CircleCheck, Info, TriangleAlert, X } from "lucide-react";

import { connectToastBus } from "./toastBus";
import { ToastContext, type ToastInput } from "./useToast";

type Toast = ToastInput & { id: string };

/** Successes announce and leave; failures stay until they are acknowledged. */
const DISMISS_AFTER: Record<ToastInput["tone"], number | null> = {
  success: 6_000,
  info: 6_000,
  error: null,
};

const MAX_VISIBLE = 4;

/**
 * The toast's own look (docs/design-system.md §11). Written here rather than in
 * the stylesheet so that a component added after this one does not have to be
 * read against fourteen files that override each other by source order.
 *
 * `--surface-raised` and not `--surface`: this genuinely floats, and in the
 * dark theme the tone step IS the elevation — a layer that only darkens the
 * ground behind it is invisible (§8). The 1px `--line` border is required for
 * the same reason, and is why `--elev-4` is a cue here rather than the only
 * one. `border-solid` is explicit because Tailwind's preflight is deliberately
 * not imported (see src/styles/index.css): `border` sets a width, not a style.
 */
const TOAST =
  "border-line bg-surface-raised text-ink shadow-elev-4 pointer-events-auto" +
  " grid grid-cols-[auto_minmax(0,1fr)_auto] items-start gap-3 rounded-lg" +
  " border border-solid border-l-[3px] px-4 py-3";

/** Tone shows in the left edge and the icon, and nowhere else. */
const TONE: Record<ToastInput["tone"], { edge: string; icon: string }> = {
  success: { edge: "border-l-success", icon: "text-success" },
  info: { edge: "border-l-accent", icon: "text-accent" },
  error: { edge: "border-l-danger", icon: "text-danger" },
};

const icons = {
  success: CircleCheck,
  info: Info,
  error: TriangleAlert,
};

/**
 * Tells people that work they started has finished, wherever they happen to be.
 *
 * Long AI jobs were previously announced only by a status row disappearing, or
 * by a browser notification the person had to opt into, so completions went
 * unnoticed. Mounted once, above the router, so any component can publish.
 *
 * The stack sits bottom-left: bottom-right is taken by the stale-content flag
 * and top-right by the notification popover.
 */
export function Toaster({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const timers = useRef(new Map<string, ReturnType<typeof setTimeout>>());
  const sequence = useRef(0);

  const dismiss = useCallback((id: string) => {
    const timer = timers.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timers.current.delete(id);
    }
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const show = useCallback((input: ToastInput) => {
    sequence.current += 1;
    const id = `toast-${sequence.current}`;
    setToasts((current) => {
      // A keyed toast replaces its predecessor rather than stacking beside it.
      const kept = input.key ? current.filter((toast) => toast.key !== input.key) : current;
      return [...kept, { ...input, id }].slice(-MAX_VISIBLE);
    });
    const after = DISMISS_AFTER[input.tone];
    if (after !== null) {
      timers.current.set(id, setTimeout(() => dismiss(id), after));
    }
  }, [dismiss]);

  // Lets the mutation cache, which lives outside the tree, publish failures.
  useEffect(() => connectToastBus(show), [show]);

  useEffect(() => {
    const pending = timers.current;
    return () => {
      pending.forEach((timer) => clearTimeout(timer));
      pending.clear();
    };
  }, []);

  const value = useMemo(() => ({ show }), [show]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      {/* Politeness is declared per toast rather than on the container below.
          A container-level aria-live applies to everything inside it, so a
          failed save announced the same way as "Draft saved" — it waited for
          whatever the screen reader was already reading and could be dropped
          entirely. role="alert" carries assertive politeness of its own; the
          visual stack is unchanged and still ordered by time, not by tone. */}
      {createPortal(
        <div
          // z-index from the named scale (§10.3). It was a bare 60, which is
          // above everything in the system including the scale's own ceiling.
          // The insets are `max(1rem, env(safe-area-inset-*))` rather than a
          // flat 1rem: this is the one fixed layer that sits at the bottom of
          // the viewport, and on a phone with a home indicator a flat 16px puts
          // the dismiss button under it — a toast that cannot be dismissed on
          // the device where the stack is narrowest. `env()` resolves to 0
          // everywhere else, so the desktop spacing is unchanged.
          className="pointer-events-none fixed bottom-[max(1rem,env(safe-area-inset-bottom))] left-[max(1rem,env(safe-area-inset-left))] z-[var(--z-top)] grid w-[min(24rem,calc(100vw-2rem))] gap-2 max-sm:right-[max(1rem,env(safe-area-inset-right))] max-sm:w-auto"
        >
          {toasts.map((toast) => {
            const Icon = icons[toast.tone];
            return (
              <div
                className={`${TOAST} ${TONE[toast.tone].edge}`}
                key={toast.id}
                role={toast.tone === "error" ? "alert" : "status"}
              >
                {/* The tone is carried by the edge and this glyph and nowhere
                    else — the title is never coloured, so a red-green
                    confusion loses nothing (§4.5). */}
                <Icon className={`mt-0.5 shrink-0 ${TONE[toast.tone].icon}`} size={18} aria-hidden="true" />
                <div className="grid min-w-0 gap-0.5">
                  <strong className="text-body text-ink font-semibold">{toast.title}</strong>
                  {toast.message && (
                    <span className="text-ink-muted text-meta [overflow-wrap:anywhere]">
                      {toast.message}
                    </span>
                  )}
                  {toast.to && (
                    <Link
                      className="text-accent hover:text-accent-strong text-meta mt-0.5 flex min-h-6 w-fit items-center font-semibold underline underline-offset-2"
                      to={toast.to}
                      onClick={() => dismiss(toast.id)}
                    >
                      {toast.linkLabel ?? "Open"}
                    </Link>
                  )}
                </div>
                {/* 32x32, the icon-button floor (§6). It was 28. */}
                <button
                  type="button"
                  className="text-ink-muted hover:text-ink hover:[background-color:color-mix(in_srgb,var(--accent)_10%,var(--surface-raised))] grid min-h-8 min-w-8 cursor-pointer place-items-center rounded-sm border-0 bg-transparent transition-colors duration-[var(--motion-fast)] ease-out motion-reduce:transition-none"
                  aria-label={`Dismiss: ${toast.title}`}
                  onClick={() => dismiss(toast.id)}
                >
                  <X size={16} aria-hidden="true" />
                </button>
              </div>
            );
          })}
        </div>,
        document.body,
      )}
    </ToastContext.Provider>
  );
}
