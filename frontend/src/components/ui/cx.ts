/**
 * Joins class names, dropping anything falsy.
 *
 * Every primitive builds its class string from a recipe plus whatever the
 * caller passed, and the caller's string always goes last so a screen can
 * still override a single property without reaching for `!important`.
 *
 * Deliberately not `clsx`: the whole of it is three lines, and the primitives
 * only ever pass strings and conditionals.
 */
export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}
