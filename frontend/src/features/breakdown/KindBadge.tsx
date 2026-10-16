import { Wrench } from "lucide-react";

import type { Feature } from "../../api/client";
import { Badge } from "../../components/ui";
import { KIND_LABEL } from "./labels";

/**
 * The SAFe enabler kind of a Feature or Story.
 *
 * Business work is the default register, so it renders nothing: a badge on
 * every card would say nothing. An enabler is the exception a Product Manager
 * sequences differently, and the wrench is the second channel §4.5 requires,
 * as with `DropBadge`. `neutral` for the same reason as DropBadge: this is a
 * register, not the screen's one next action.
 */
export function KindBadge({ kind }: { kind: Feature["kind"] }) {
  if (kind === "business") return null;
  return (
    <Badge tone="neutral" icon={<Wrench aria-hidden={true} className="shrink-0" size={12} />}>
      {KIND_LABEL[kind]}
    </Badge>
  );
}
