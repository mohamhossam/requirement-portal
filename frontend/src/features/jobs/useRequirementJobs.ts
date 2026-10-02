import { createContext, useContext } from "react";
import type { RequirementJobsState } from "./RequirementJobsProvider";

export const RequirementJobsContext = createContext<RequirementJobsState | null>(null);

export function useRequirementJobs(requirementId: string) {
  const state = useContext(RequirementJobsContext);
  if (!state || state.requirementId !== requirementId) {
    throw new Error("Requirement jobs must be consumed inside their workspace provider.");
  }
  return state;
}
