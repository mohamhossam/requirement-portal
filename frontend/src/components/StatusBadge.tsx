import { Check, PenLine, Sparkles, TriangleAlert } from "lucide-react";
import type { ComponentType } from "react";

import type { GenerationStatus } from "../api/client";
import { STATUS_LABEL } from "./statusLabels";
import { Badge, type BadgeTone } from "./ui/Badge";

/**
 * Where a backlog item came from and where it stands.
 *
 * Built on `Badge`, so the second channel is not optional: the old markup hung
 * a `.status-mark` dot off `.status-{status}` and let colour do the rest, which
 * meant "Approved" and "Needs revision" differed by hue alone. Each state now
 * carries a glyph of its own shape (§4.5).
 *
 * The tone mapping is a provenance reading, not a severity one. `generated` is
 * the accent because that is the product's provenance ground for AI-written
 * content, and `edited` is the neutral register because a human wrote it —
 * neither is better than the other, and neither is a status.
 */
type Presentation = {
  label: string;
  tone: BadgeTone;
  icon: ComponentType<{ size?: number; className?: string; "aria-hidden"?: boolean }>;
};

const PRESENTATION: Record<GenerationStatus, Presentation> = {
  generated: { label: STATUS_LABEL.generated, tone: "neutral", icon: Sparkles },
  edited: { label: STATUS_LABEL.edited, tone: "neutral", icon: PenLine },
  approved: { label: STATUS_LABEL.approved, tone: "success", icon: Check },
  needs_revision: { label: STATUS_LABEL.needs_revision, tone: "warning", icon: TriangleAlert },
};

export function StatusBadge({ status }: { status: GenerationStatus }) {
  const { label, tone, icon: Icon } = PRESENTATION[status];
  return (
    // `data-status` rather than the old `.status status-{status}` pair: the
    // state is still addressable — by a test, or by a screen that needs to
    // align a column of them — without reintroducing a class four stylesheets
    // have an opinion about.
    <Badge
      data-status={status}
      icon={<Icon aria-hidden={true} className="shrink-0" size={12} />}
      tone={tone}
    >
      {label}
    </Badge>
  );
}
