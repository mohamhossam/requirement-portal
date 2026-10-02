/**
 * The part of a Story's voice that tells it apart from its siblings.
 *
 * Every generated Story opens with the same construction — "As a SMB customer,
 * I want …" — so a 2-line clamp in a 240px rail produced rows whose visible
 * text was identical and whose distinguishing words sat inside the ellipsis.
 * The list a reviewer navigates by was, in practice, unreadable.
 *
 * Presentation only, and only where the label is a navigation target: the card
 * always shows the full voice as written, and every truncated label keeps the
 * whole sentence in `title` so nothing is lost to a hover or a screen reader.
 * If the voice does not match the construction it is returned untouched, which
 * is the right answer for a human-edited Story that no longer reads like one.
 */
const VOICE = /^\s*As\s+(?:an?|the)\s+[^,]+,\s*I\s+want\s+(?:to\s+)?(.+)$/i;

export function storyGist(voice: string): string {
  const match = VOICE.exec(voice);
  const rest = match?.[1]?.trim();
  if (!rest) return voice;
  return rest.charAt(0).toUpperCase() + rest.slice(1);
}
