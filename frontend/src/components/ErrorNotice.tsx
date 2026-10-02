/**
 * The inline alert beside a control that just refused.
 *
 * It reports and stops; where content never arrived and a person needs a way
 * forward, `ErrorState` is the block to reach for instead.
 *
 * Two channels, never colour alone (docs/design-system.md §4.5): the 3px
 * `--danger` left edge alongside the wash, and a sentence naming the failure.
 * In utilities rather than through `.error-notice`, which three stylesheets
 * redeclare — one of them with two hardcoded hex values that predate the
 * palette.
 */
export function ErrorNotice({ message }: { message: string }) {
  return (
    <div
      className="error-notice border-line bg-danger-wash my-3 grid gap-1 rounded-sm border border-solid border-l-[3px] border-l-[var(--danger)] px-3 py-2"
      role="alert"
    >
      <strong className="text-danger text-body">We couldn’t complete that action.</strong>
      <span className="text-ink-soft text-body">{message}</span>
    </div>
  );
}
