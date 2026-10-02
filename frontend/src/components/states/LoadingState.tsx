import type { ReactNode } from "react";

import { Skeleton, type SkeletonVariant } from "../Skeleton";

/**
 * "Not here yet", as a block rather than as a bare Skeleton.
 *
 * The Skeleton draws the shape; this gives it the padding, the optional caption
 * and — for `page` — the full-height frame that a route still loading needs, so
 * that twenty call sites stop each inventing their own wrapper. Reserving the
 * space is also how the system meets the no-content-jumping rule
 * (docs/design-system.md §9): the bars are sized to what is coming.
 *
 * `page` is the whole route opening and centres itself in the frame. Every other
 * variant sits in the flow where the content will land.
 */
export function LoadingState({
  label,
  variant = "panel",
  bars,
  caption,
}: {
  /** What is loading, as a sentence. Announced once through the Skeleton. */
  label: string;
  variant?: SkeletonVariant;
  bars?: number;
  /** Visible text beneath the bars, when the wait deserves a word. */
  caption?: ReactNode;
}) {
  if (variant === "page") {
    return (
      <div
        className="loading-state grid min-h-[60dvh] place-content-center justify-items-center gap-4 p-10"
        data-state="loading"
      >
        <Skeleton label={label} variant="page" bars={bars} />
        {caption ? <p className="text-ink-muted text-meta m-0">{caption}</p> : null}
      </div>
    );
  }
  return (
    <div className="loading-state grid gap-3 p-4" data-state="loading">
      <Skeleton label={label} variant={variant} bars={bars} />
      {caption ? <p className="text-ink-muted text-meta m-0">{caption}</p> : null}
    </div>
  );
}
