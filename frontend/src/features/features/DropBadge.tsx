import { CalendarClock, Milestone } from "lucide-react";

import type { Feature } from "../../api/client";
import { Badge } from "../../components/ui";
import { DROP_LABEL } from "../breakdown/labels";

/**
 * Which delivery drop a Feature belongs to.
 *
 * Deliberately `neutral`, not `accent`: this is a register — which drop — and
 * docs/design-system.md §4.4 spends `--accent` once per screen, on the next
 * action. The Approve and Continue reviewing buttons already spend it, so an
 * accent badge beside them would leave two things on the page claiming to be
 * the one that matters. The glyph carries the difference instead, which is also
 * the second channel §4.5 requires.
 */
export function DropBadge({ drop }: { drop: Feature["delivery_drop"] }) {
  const mvp = drop === "mvp";
  return (
    <Badge
      tone="neutral"
      icon={mvp
        ? <Milestone aria-hidden={true} className="shrink-0" size={12} />
        : <CalendarClock aria-hidden={true} className="shrink-0" size={12} />}
    >
      {/* "MVP" and "Later drop" were delivery jargon; which release is the fact. */}
      {DROP_LABEL[drop]}
    </Badge>
  );
}
