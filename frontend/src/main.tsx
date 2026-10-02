import { MutationCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import { App } from "./app/App";
import { UnsavedChangesProvider } from "./app/UnsavedChangesProvider";
import { Toaster } from "./components/Toaster";
import { ApiError } from "./api/errors";
import { mutationErrorToast } from "./app/mutationErrors";
import { publishToast } from "./components/toastBus";
import { AuthGate, AuthProvider } from "./auth/AuthProvider";
// Three faces, self-hosted (design-system.md §5). PRODUCT.md makes
// deterministic offline operation a first-class mode, so a font CDN is not
// permissible — these resolve to files Vite fingerprints into the bundle.
// Only the weights the type scale actually names are shipped, and
// `font-synthesis: none` in tokens.css keeps the browser from faking a
// missing one.
//
// Public Sans — interface: every control, label, table, nav item, badge.
import "@fontsource/public-sans/latin-400.css";
import "@fontsource/public-sans/latin-500.css";
import "@fontsource/public-sans/latin-600.css";
import "@fontsource/public-sans/latin-700.css";
// Source Serif 4 — document: requirement text, findings, generated narrative.
import "@fontsource/source-serif-4/latin-400.css";
import "@fontsource/source-serif-4/latin-400-italic.css";
import "@fontsource/source-serif-4/latin-600.css";
// IBM Plex Mono — machine strings only: IDs, checksums, fingerprints, diffs.
import "@fontsource/ibm-plex-mono/latin-400.css";
import "@fontsource/ibm-plex-mono/latin-500.css";
import "./styles/index.css";

const queryClient = new QueryClient({
  // Every failed action gets a visible home, whatever the panel it came from.
  mutationCache: new MutationCache({
    onError: (error, _variables, _context, mutation) => {
      const notice = mutationErrorToast(error, mutation.options.meta);
      if (notice) publishToast(notice);
    },
  }),
  defaultOptions: {
    queries: {
      staleTime: 10_000,
      // Retry only what retrying can fix. 4xx must surface immediately: the
      // workspace relies on 409 version conflicts reaching the editor so it
      // can reconcile, and a retried 409 would just race the same conflict.
      retry: (failureCount, error) => {
        if (failureCount >= 2) return false;
        const status = error instanceof ApiError ? error.status : 0;
        return status === 0 || status >= 500;
      },
    },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <AuthGate>
            <Toaster>
              <UnsavedChangesProvider><App /></UnsavedChangesProvider>
            </Toaster>
          </AuthGate>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  </StrictMode>,
);
