import type { ReactNode } from "react";

import { EmptyState } from "../EmptyState";
import type { SkeletonVariant } from "../Skeleton";
import type { AsyncStatus } from "./asyncStatus";
import { ErrorState } from "./ErrorState";
import { LoadingState } from "./LoadingState";

/**
 * The one shape of "loading / failed / nothing here / here it is".
 *
 * Every list, panel and page in the app wrote this branch by hand, and they
 * disagreed: some showed a skeleton and some a paragraph, some reported a failed
 * read as an inline notice under a rendered-empty table, and several had no
 * empty state at all. This is that branch, once.
 *
 * Deliberately not given a query object. It takes a status and slots, so it
 * stays a presentation component: what to fetch, when to retry and what counts
 * as empty are the caller's, and this only decides which of the four to draw.
 * `asyncStatus` is the tiny adapter for a TanStack query at the call site.
 *
 * One thing to know at the call site: `children` is a prop, so React builds it
 * before this component decides anything. It has to be safe to *construct* while
 * the data is still absent — read through `?.`, or default the list — even though
 * it will not be rendered until the status says `ready`.
 */
export function AsyncState({
  status,
  loading,
  error,
  empty,
  onRetry,
  headingLevel = "h3",
  children,
}: {
  status: AsyncStatus;
  loading: { label: string; variant?: SkeletonVariant; bars?: number; caption?: ReactNode };
  /** The message from the failed read. Required for `status: "error"` to say anything. */
  error?: { message: string; title?: string; action?: ReactNode };
  /** Omitted when a caller draws its own empty case, or has none. */
  empty?: { title: string; message: string; action?: ReactNode; icon?: ReactNode };
  onRetry?: () => void;
  headingLevel?: "h2" | "h3" | "h4";
  children: ReactNode;
}) {
  if (status === "pending") return <LoadingState {...loading} />;
  if (status === "error") {
    return (
      <ErrorState
        headingLevel={headingLevel}
        title={error?.title}
        message={error?.message ?? "The request did not complete."}
        action={error?.action}
        onRetry={onRetry}
      />
    );
  }
  if (status === "empty" && empty) return <EmptyState headingLevel={headingLevel} {...empty} />;
  return <>{children}</>;
}
