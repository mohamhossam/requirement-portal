import { useEffect, useRef, type KeyboardEvent, type MouseEvent, type ReactNode, type RefObject } from "react";
import { createPortal } from "react-dom";

/**
 * The one modal behaviour in the app.
 *
 * Five dialogs had grown their own: two native <dialog> elements with
 * near-identical hand-written logic, and three div-based ones missing pieces of
 * it — one with no focus trap, one with neither a trap nor a way out by
 * keyboard. This owns the behaviour; callers keep their own content and CSS.
 *
 * Nesting works because showModal() stacks in the top layer: a confirmation
 * opened inside the source drawer traps its own Tab, and Escape dismisses only
 * the topmost. That is what ConfirmDialog's old `focused` prop was hand-rolling.
 *
 * Styling used to be passed through only: the sheet-shaped dialogs already had
 * .workspace-drawer and .analysis-sources-dialog, and the centred ones shared
 * .confirm-dialog. That still works and is still the default — `variant` is
 * "bare" unless a caller asks otherwise, so every existing dialog renders
 * exactly as it did. New work takes `variant="dialog"` or `variant="drawer"`
 * and gets the chrome from docs/design-system.md §8 and §11: `--radius-lg`, a
 * `--surface-raised` ground with its 1px `--line` border, `--elev-4` for a
 * modal and `--elev-3` for a drawer, and the `--scrim` behind both.
 *
 * Centring comes from the user agent's `dialog:modal { inset: 0; margin: auto }`.
 *
 * `portal` is not about stacking. showModal() promotes the element to the top
 * layer, which paints above everything regardless of DOM ancestry or z-index,
 * so nothing needs a portal to be seen. What a portal changes is which
 * DESCENDANT SELECTORS match: the drawer renders inside .breakdown-shell, whose
 * `.breakdown-shell .button` rule restyles every button under it, so the drawer
 * has always escaped to document.body to keep the global button style. Each
 * caller therefore keeps the placement it had, and a confirmation raised from
 * inside the drawer stays a descendant of it, which its smoke test asserts.
 */

const FOCUSABLE = [
  "button:not(:disabled)",
  "a[href]",
  "input:not(:disabled)",
  "textarea:not(:disabled)",
  "select:not(:disabled)",
  "summary",
  '[tabindex]:not([tabindex="-1"])',
].join(", ");

/**
 * Both floating variants keep a 1px border as well as their shadow. In the dark
 * theme the tone step *is* the elevation — a layer that only darkens the ground
 * behind it is invisible — so the border is not decoration (§8).
 */
/*
 * `overscroll-contain` on both: each variant scrolls its own content, and
 * without it a flick or a wheel that reaches the end of the dialog keeps going
 * into the page behind the scrim — so a person closes the dialog to find the
 * list they came from has moved. It is the scroll equivalent of the focus trap
 * above, and it matters most on the drawer, which is full-height and next to a
 * long workspace.
 */
const VARIANT = {
  bare: "",
  dialog:
    "border-line bg-surface-raised text-ink shadow-elev-4 backdrop:bg-scrim" +
    " max-h-[calc(100vh-4rem)] overflow-auto overscroll-contain" +
    " rounded-lg border border-solid p-6",
  // Side and size are not in here: see DRAWER_SIDE and DRAWER_SIZE.
  drawer:
    "border-line bg-surface-raised text-ink shadow-elev-3 backdrop:bg-scrim" +
    " h-full max-h-full max-w-full overflow-auto overscroll-contain border-y-0 border-solid",
} as const;

export type ModalVariant = keyof typeof VARIANT;

/**
 * Which edge a drawer comes from, and how wide it is, are props rather than
 * caller classes on purpose. A class that sets a property the primitive already
 * sets — `p-4` against `p-6`, `border-l-0` against `border-l` — does not win by
 * coming last in the attribute; it wins or loses by Tailwind's output order.
 * The navigation drawer lost that way for as long as it existed: it asked for
 * 18rem and rendered 30rem wide, which at 375px is the whole screen.
 *
 * Each class below sets properties nothing else here sets. `--radius-lg` goes
 * on the open edge only (§7): the other edge is flush with the viewport.
 */
const DRAWER_SIDE = {
  right: "mr-0 ml-auto border-r-0 border-l rounded-l-lg",
  left: "ml-0 mr-auto border-l-0 border-r rounded-r-lg",
} as const;
/**
 * A dialog's width, as a prop for the same reason as the drawer's: a caller's
 * `w-*` against the primitive's own loses or wins by output order, not intent.
 * `wide` is for a dialog that holds a form of several parts side by side.
 */
const DIALOG_SIZE = {
  md: "w-[min(34rem,calc(100vw-2rem))]",
  wide: "w-[min(64rem,calc(100vw-2rem))]",
} as const;

const DRAWER_SIZE = {
  /* Source, People, evidence — content a person reads. */
  md: "w-[min(30rem,100vw)] p-6",
  /* An editor with fields side by side — a system and its capabilities. */
  lg: "w-[min(46rem,100vw)] p-6",
  /* Navigation — a list of four destinations. */
  sm: "w-[min(18rem,85vw)] p-4",
} as const;

export function Modal({
  children,
  onClose,
  className,
  variant = "bare",
  side = "right",
  size = "md",
  labelledBy,
  label,
  describedBy,
  restoreFocusTo,
  initialFocus,
  portal = false,
  closeOnOutsideClick = true,
}: {
  children: ReactNode;
  onClose: () => void;
  className?: string;
  /**
   * "bare" — the historical behaviour, and the default: no chrome, the caller's
   * class is the whole look. "dialog" and "drawer" apply the designed chrome.
   * `className` still lands after it, so a caller can adjust one property.
   */
  variant?: ModalVariant;
  /** Drawer only: the edge it opens from. */
  side?: keyof typeof DRAWER_SIDE;
  /**
   * Drawer: `sm` for navigation, `md` for anything a person reads, `lg` for an
   * editor whose fields sit side by side.
   * Dialog: `md` by default, `wide` for a form with parts side by side.
   */
  size?: keyof typeof DRAWER_SIZE | keyof typeof DIALOG_SIZE;
  /** Id of the element naming this dialog. Use `label` when there is no heading. */
  labelledBy?: string;
  label?: string;
  describedBy?: string;
  /** Where focus goes on close. Defaults to whatever was focused when it opened. */
  restoreFocusTo?: HTMLElement | null;
  /**
   * What to focus on open, when it should not be the first focusable control.
   * React's autoFocus prop cannot do this: it calls focus() imperatively rather
   * than setting the attribute showModal() looks for, so showModal then moves
   * focus to the first control anyway.
   */
  initialFocus?: RefObject<HTMLElement | null>;
  /** Render into document.body, to escape ancestor descendant selectors. */
  portal?: boolean;
  closeOnOutsideClick?: boolean;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  // Captured once: focus goes back to whatever opened this dialog.
  const opener = useRef(restoreFocusTo ?? document.activeElement);
  const wanted = useRef(initialFocus);

  useEffect(() => {
    const element = dialog.current!;
    const target = opener.current;
    element.showModal();
    // After showModal, which has its own opinion about where focus lands.
    wanted.current?.current?.focus();
    return () => {
      element.close();
      if (target instanceof HTMLElement && target.isConnected) target.focus();
    };
  }, []);

  // Real browsers trap focus natively once the dialog is in the top layer. This
  // keeps the wrap honest in jsdom, and it is what the smoke specs assert.
  const trapTab = (event: KeyboardEvent<HTMLDialogElement>) => {
    if (event.key !== "Tab") return;
    // A nested dialog handles its own Tab; the one beneath must not also act.
    event.stopPropagation();
    const items = [...event.currentTarget.querySelectorAll<HTMLElement>(FOCUSABLE)]
      .filter((item) => item.getClientRects().length > 0);
    const first = items[0];
    const last = items.at(-1);
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last?.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first?.focus();
    }
  };

  // A click on the dialog element itself, landing outside its painted box, is a
  // click on the backdrop: the backdrop has no element of its own to listen on.
  const closeOnBackdrop = (event: MouseEvent<HTMLDialogElement>) => {
    if (!closeOnOutsideClick || event.target !== event.currentTarget) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    const outside =
      event.clientX < bounds.left ||
      event.clientX > bounds.right ||
      event.clientY < bounds.top ||
      event.clientY > bounds.bottom;
    if (outside) onClose();
  };

  const element = (
    <dialog
      ref={dialog}
      className={
        [
          VARIANT[variant],
          variant === "drawer" && DRAWER_SIDE[side],
          variant === "drawer" && DRAWER_SIZE[size === "wide" ? "md" : size],
          variant === "dialog" && DIALOG_SIZE[size === "sm" || size === "lg" ? "md" : size],
          className,
        ]
          .filter(Boolean)
          .join(" ") || undefined
      }
      aria-labelledby={labelledBy}
      aria-label={label}
      aria-describedby={describedBy}
      onCancel={(event) => {
        // Escape. Cancel the native close so React owns unmounting.
        event.preventDefault();
        event.stopPropagation();
        onClose();
      }}
      onClick={closeOnBackdrop}
      onKeyDown={trapTab}
    >
      {children}
    </dialog>
  );

  return portal ? createPortal(element, document.body) : element;
}

/**
 * The dialog's heading row.
 *
 * `id` is required and not generated here, because the same id has to reach the
 * Modal as `labelledBy` — a dialog labelled by nothing announces as "dialog"
 * and a person tabbing into it has no idea what they are in (§13, item 10).
 */
export function ModalHeader({
  id,
  title,
  eyebrow,
  description,
  descriptionId,
}: {
  id: string;
  title: ReactNode;
  eyebrow?: ReactNode;
  description?: ReactNode;
  descriptionId?: string;
}) {
  return (
    <header className="mb-4 grid gap-1">
      {eyebrow && <p className="text-label text-ink-muted m-0">{eyebrow}</p>}
      <h2 className="text-headline text-ink m-0" id={id}>
        {title}
      </h2>
      {description && (
        <p className="text-ink-muted text-body m-0" id={descriptionId}>
          {description}
        </p>
      )}
    </header>
  );
}

export function ModalBody({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={["text-body text-ink-soft grid gap-4", className].filter(Boolean).join(" ")}>{children}</div>;
}

/**
 * Actions, right-aligned, with the confirming one last in DOM order — which is
 * why ConfirmDialog has to ask for the opening focus explicitly.
 */
export function ModalFooter({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <footer
      className={["mt-6 flex flex-wrap items-center justify-end gap-2", className]
        .filter(Boolean)
        .join(" ")}
    >
      {children}
    </footer>
  );
}
