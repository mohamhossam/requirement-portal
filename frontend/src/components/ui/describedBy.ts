import { cx } from "./cx";

/**
 * What a control should point `aria-describedby` at. Order matters: the hint
 * explains the field, the error explains what went wrong with it.
 */
export function describedBy(
  hint: unknown,
  hintId: string,
  error: unknown,
  errorId: string,
  caller?: string,
): string | undefined {
  return cx(caller, hint ? hintId : "", error ? errorId : "") || undefined;
}
