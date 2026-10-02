import type { ToastInput } from "./useToast";

type Sink = (toast: ToastInput) => void;

let sink: Sink | null = null;

/**
 * Lets code outside the React tree publish a notice.
 *
 * The QueryClient and its MutationCache are built at module scope, so they
 * cannot call useToast. The Toaster connects itself on mount instead. Nothing
 * inside a component should use this: useToast is there for that.
 */
export function connectToastBus(next: Sink) {
  sink = next;
  return () => {
    if (sink === next) sink = null;
  };
}

export function publishToast(toast: ToastInput) {
  sink?.(toast);
}
