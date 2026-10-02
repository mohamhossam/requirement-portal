import type { RequirementAnalysis } from "../../api/client";

type HumanAnswer = RequirementAnalysis["clarifications"][number];
export function humanEvidence(analysis: RequirementAnalysis, kind: string, subject: string): HumanAnswer[] {
  const key = `${kind}:${subject.trim().toLowerCase().replace(/\s+/g, " ")}`;
  const reference = analysis.clarification_evidence?.find((item) => item.evidence_key === key);
  return (reference?.clarification_numbers ?? []).flatMap((number) => {
    const answer = analysis.clarifications[number - 1];
    return answer ? [answer] : [];
  });
}

export function when(value: string | null | undefined): string {
  return value ? new Date(value).toLocaleString() : "an unrecorded date";
}

/** The section heading both columns share, so neither reads as the other's child. */
