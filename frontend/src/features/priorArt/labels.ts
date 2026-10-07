import type { PriorArt } from "../../api/client";

/**
 * What the Knowledge step says about similar past requirements (Knowledge Center E2).
 *
 * Every word the panel shows about a status or a work item comes from here: no raw enum
 * value reaches the page.
 */

export const PRIOR_ART_HEADING = "Similar past requirements";

export const PRIOR_ART_DESCRIPTION: Partial<Record<PriorArt["status"], string>> = {
  not_checked: "This requirement has not been compared with delivered work from old BRDs yet.",
  checking: "Comparing this requirement with delivered work from old BRDs. You can keep working meanwhile.",
  waiting: "The comparison is queued behind this hour’s other checks and starts by itself.",
  current: "Delivered work from old BRDs that resembles this requirement.",
  out_of_date: "Historic requirements changed since this was compared. It is compared again when you open this step.",
  failed: "The last comparison stopped without finishing. It will not start again by itself.",
};

/** Said once, under the heading, whatever the status. */
export const REFERENCE_ONLY = "Reference only: it never affects confirmation.";

export const NO_MATCHES = "No delivered requirement looks like this one.";

export const WORK_ITEM_TYPE: Record<"epic" | "feature" | "user_story", string> = {
  epic: "Epic",
  feature: "Feature",
  user_story: "User Story",
};

export const PASSAGE_SOURCE: Record<"historic_brd" | "historic_backlog", string> = {
  historic_brd: "From the BRD",
  historic_backlog: "From Azure DevOps",
};

/** The panel stays out of the way when there is nothing to compare with, or it is off. */
export function priorArtShown(status: PriorArt["status"]): boolean {
  return status !== "disabled" && status !== "no_historic_knowledge";
}
