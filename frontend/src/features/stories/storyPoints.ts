/** The relative scale; anything bigger is a Story to split (ADR-0121). */
export const STORY_POINT_SCALE = [1, 2, 3, 5, 8, 13] as const;

/** One wording for "no confirmed size", wherever it is said of one Story. */
export const NOT_SIZED = "Not sized yet";

/** The same, said of a set of Stories with none sized. */
export const NONE_SIZED = "None sized yet";

/** "5 points", "1 point": the size in words, never a bare number. */
export function pointsLabel(points: number) {
  return `${points} point${points === 1 ? "" : "s"}`;
}

/** Who decided a size, said the same way on the card, the list and Review & approve. */
export function decidedBy(basis: "accepted_suggestion" | "team_entered", name: string) {
  return basis === "accepted_suggestion" ? `AI suggestion accepted by ${name}` : `Set by ${name}`;
}

/**
 * Sizing an approved Story reopens its approval (ADR-0121). The dialog names
 * the act actually happening — a first size, a change, or clearing one.
 */
export function reopenApproval(current: number | null, next: number | null) {
  if (next == null) {
    return {
      title: "Clear an approved Story's size?",
      message:
        "The size is part of what this Story's approval covers. Clearing it reopens the approval, so the Story needs approving again on Review & approve.",
      confirmLabel: "Clear size",
    };
  }
  if (current == null) {
    return {
      title: "Size an approved Story?",
      message:
        "The size becomes part of what this Story's approval covers. Setting it reopens the approval, so the Story needs approving again on Review & approve.",
      confirmLabel: "Set size",
    };
  }
  return {
    title: "Change an approved Story's size?",
    message:
      "The size is part of what this Story's approval covers. Changing it reopens the approval, so the Story needs approving again on Review & approve.",
    confirmLabel: "Change size",
  };
}

/** One Story, as the size section shows it for comparison. */
export type SizeSibling = {
  id: string;
  gist: string;
  points: number | null;
  suggested: number | null;
};

/** Smallest first, by confirmed size or else the AI's; Stories with neither last. */
export function byRelativeSize(items: SizeSibling[]): SizeSibling[] {
  const rank = (item: SizeSibling) => item.points ?? item.suggested ?? Number.POSITIVE_INFINITY;
  return [...items].sort((a, b) => rank(a) - rank(b));
}
