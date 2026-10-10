import { createContext, useContext } from "react";

export type ToastTone = "success" | "error" | "info";

export type ToastInput = {
  tone: ToastTone;
  title: string;
  message?: string;
  /** The API's correlation ID of a failure, from `errorReference(error)`. */
  reference?: string | null;
  /** In-app destination for the toast's link, if the result is worth opening. */
  to?: string;
  linkLabel?: string;
  /**
   * Collapses repeats. A toast published with a key already on screen replaces
   * it instead of stacking, so a retried job does not pile up notices.
   */
  key?: string;
};

export type ToastApi = { show: (toast: ToastInput) => void };

const noop: ToastApi = { show: () => undefined };

export const ToastContext = createContext<ToastApi | null>(null);

/**
 * Publishes transient notices. Outside a Toaster this is a no-op, so components
 * and tests can render without one.
 */
export function useToast(): ToastApi {
  return useContext(ToastContext) ?? noop;
}
