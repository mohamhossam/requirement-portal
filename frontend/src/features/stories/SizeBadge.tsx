import { ChartNoAxesColumnIncreasing } from "lucide-react";

import { Badge } from "../../components/ui";
import { pointsLabel } from "./storyPoints";

/**
 * A Story's confirmed size (ADR-0121).
 *
 * Only a size the team confirmed renders: an AI suggestion is not a size yet,
 * and an unsized Story shows nothing rather than a zero. `neutral` with the
 * rising bars as its second channel, like `KindBadge` and `DropBadge`: a size is a
 * register, not the screen's one next action, so it never spends the accent.
 * Rising bars say "relative size"; a diagonal ruler looked like the "Edited" pen
 * and a weight like a padlock at 12px.
 */
export function SizeBadge({ points }: { points: number | null | undefined }) {
  if (points == null) return null;
  return (
    <Badge tone="neutral" icon={<ChartNoAxesColumnIncreasing aria-hidden={true} className="shrink-0" size={12} />}>
      {pointsLabel(points)}
    </Badge>
  );
}
