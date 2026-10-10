/**
 * The API's correlation ID for a failure (`errorReference(error)`), so a person
 * can quote it and an operator can find the request in the logs.
 *
 * Mono, because it is a machine string (docs/design-system.md §5), and
 * `select-all`, so one click selects the whole ID to copy. Renders nothing when
 * the failure never reached the API and so has no ID.
 */
export function ErrorReference({
  id,
  tone = "text-ink-soft",
}: {
  id: string | null | undefined;
  /** The ink of the surrounding message, so the reference reads as part of it. */
  tone?: "text-ink-soft" | "text-ink-muted";
}) {
  if (!id) return null;
  return (
    <span className={`${tone} text-meta [overflow-wrap:anywhere]`}>
      Reference: <code className="font-mono select-all">{id}</code>
    </span>
  );
}
