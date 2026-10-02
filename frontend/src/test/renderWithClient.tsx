import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { RequirementJobsProvider } from "../features/jobs/RequirementJobsProvider";

export function renderWithClient(ui: ReactElement, requirementId?: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return {
    queryClient,
    ...render(<QueryClientProvider client={queryClient}>{requirementId ? <RequirementJobsProvider requirementId={requirementId}>{ui}</RequirementJobsProvider> : ui}</QueryClientProvider>),
  };
}

export function renderWithJobs(ui: ReactElement) {
  return renderWithClient(ui, "req-1");
}
