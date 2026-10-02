import { AlertTriangle } from "lucide-react";

import type { Staleness } from "../api/client";

const reasonCopy: Record<Staleness["reason"], string> = {
  requirement_changed: "the requirement changed after this was generated",
  epic_changed: "the parent Epic changed after this was generated",
  feature_changed: "the parent Feature changed after this was generated",
};

/**
 * What to do about it. The notice named the problem and stopped, so a reviewer
 * met the one state this product exists to flag and was given no way out.
 */
const remedyCopy: Record<Staleness["reason"], string> = {
  requirement_changed: "Read it against the updated requirement, then edit or regenerate it.",
  epic_changed: "Read it against the Epic as it is now, then edit or regenerate it.",
  feature_changed: "Read it against the Feature as it is now, then edit or regenerate it.",
};

/**
 * The moment PRODUCT.md Principle 4 exists to protect: an upstream edit has
 * invalidated approved downstream work, and the product flags rather than
 * overwrites.
 *
 * It used to render `.stale-notice`, which hardcoded `#efc0b7` and `#84332d`
 * over `--danger-soft`. That measured about 2.0:1 in the Slate theme, so a
 * dark-theme reviewer was shown effectively nothing at the one moment that
 * matters most. It was also the wrong vocabulary: red means "this is wrong"
 * everywhere else in this system (§4.4), while staleness is `--warning` (§4.5)
 * — and the Card around it is already painted amber, so the notice and its
 * container were arguing about which status this was.
 *
 * No fill: the parent Card's wash already groups it, and a second wash inside
 * the first reads as a panel stuck to a panel. The edge and the glyph carry it.
 */
export function StalenessNotice({ stale }: { stale: Staleness }) {
  const timestamp = new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(stale.since));
  return (
    <div
      // `stale-notice` is a test hook only now: its declarations are gone from
      // 01-foundation.css and 04-modernist.css, and the chrome comes from tokens.
      className="stale-notice border-line text-body my-4 flex items-start gap-2 rounded-md border border-solid border-l-[3px] border-l-[var(--warning-edge)] px-3 py-2"
      role="status"
    >
      <AlertTriangle aria-hidden="true" className="text-warning mt-0.5 shrink-0" size={17} />
      <span className="text-ink-soft">
        <strong className="text-ink">Out of date</strong>
        {" — since "}
        {timestamp}, {reasonCopy[stale.reason]}. {remedyCopy[stale.reason]} Earlier
        versions stay in History.
      </span>
    </div>
  );
}
