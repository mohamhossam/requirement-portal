import { ApiError, errorMessage, errorReference, isAbortedRequest } from "../api/errors";
import type { ToastInput } from "../components/useToast";

/** What a mutation may declare about how its failures should be reported. */
export type MutationErrorMeta = {
  /** What the person was doing, for the notice: "Approving the Epic". */
  action?: string;
  /** Opt out when the mutation reports its own outcome some other way. */
  toastOnError?: boolean;
};

// MutationMeta is derived from Register in React Query v5, so this is the
// augmentation point; declaring `interface MutationMeta` collides with it.
declare module "@tanstack/react-query" {
  interface Register {
    mutationMeta: MutationErrorMeta;
  }
}

/**
 * A failed action must not be able to go unnoticed. Inline notices stay where
 * they are, because they carry context a toast cannot, but they live deep in
 * panels, inside collapsed disclosures and inside scrollable regions, so they
 * are not a reliable channel on their own.
 *
 * Two kinds of failure are deliberately silent here:
 *
 *   409  a version conflict. The editors reconcile these in place, and a toast
 *        saying "conflict" without the reconcile affordance beside it is worse
 *        than the inline treatment.
 *   401  an expired session, which the header already offers to renew.
 *   0    a request abandoned because the person signed out or switched identity
 *        (`request_aborted`): they did that themselves, mid-flight.
 */
export function mutationErrorToast(error: unknown, meta?: MutationErrorMeta): ToastInput | null {
  if (meta?.toastOnError === false) return null;
  if (error instanceof ApiError && (error.status === 409 || error.status === 401)) return null;
  if (isAbortedRequest(error)) return null;

  const action = meta?.action;
  return {
    tone: "error",
    title: action ? `${action} failed` : "That action could not be completed",
    message: errorMessage(error),
    reference: errorReference(error),
    // Repeated attempts at the same action replace rather than stack.
    key: `mutation-${action ?? "generic"}`,
  };
}
