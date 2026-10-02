/**
 * The list logic behind `TagInput`, in its own module so TagInput.tsx exports
 * only a component and keeps fast refresh.
 */

/** Commas and line breaks separate entries, so a pasted list arrives whole. */
export const SEPARATOR = /[,\n]/;

/** Adds what is not already there, ignoring case. */
function merge(values: string[], incoming: string[]): string[] {
  const seen = new Set(values.map((value) => value.toLocaleLowerCase()));
  const next = [...values];
  for (const raw of incoming) {
    const value = raw.trim();
    if (!value || seen.has(value.toLocaleLowerCase())) continue;
    seen.add(value.toLocaleLowerCase());
    next.push(value);
  }
  return next;
}

/** The values with any half-typed text committed: what a form saves. */
export const withDraft = (values: string[], draft: string) => merge(values, draft.split(SEPARATOR));
