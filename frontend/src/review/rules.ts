import type { Epic, Feature, FeatureSet, RequirementAnalysis, Story } from "../api/client";

export type Permission = { ok: true } | { ok: false; reason: string };

export function canApprove(item: Epic | FeatureSet["features"][number]): Permission {
  if (item.stale) {
    const source = item.stale.reason === "requirement_changed" ? "requirement" : "Epic";
    return { ok: false, reason: `Reconcile this item because its source ${source} changed.` };
  }
  if (item.status === "approved") {
    return {
      ok: false,
      reason: "This version is already approved. Regenerate or edit it before approving again.",
    };
  }
  return { ok: true };
}

export function canGenerateEpic(analysis: RequirementAnalysis | null): Permission {
  if (!analysis) {
    return { ok: false, reason: "Analyse the current requirement before generating an Epic." };
  }
  if (!analysis.human_confirmed) {
    return { ok: false, reason: "Confirm the analysis before generating an Epic." };
  }
  return { ok: true };
}

export function canDecompose(
  analysis: RequirementAnalysis | null,
  epic: Epic | null,
): Permission {
  if (!analysis) return { ok: false, reason: "Analyse the current requirement first." };
  if (!epic) return { ok: false, reason: "Generate and approve an Epic first." };
  if (epic.stale) return { ok: false, reason: "Reconcile the stale Epic before decomposing it." };
  if (epic.status !== "approved") return { ok: false, reason: "Approve the Epic first." };
  return { ok: true };
}

export function regenerationLoss(epic: Epic, features: FeatureSet | null): string | null {
  if (epic.status === "generated") return null;
  const childEffect = features?.features.length
    ? ` It will also mark ${features.features.length} Feature${features.features.length === 1 ? "" : "s"} out of date.`
    : "";
  return `This Epic has been ${epic.status}. Regenerating replaces its content and human review state.${childEffect}`;
}

export function canGenerateStories(feature: Feature): Permission {
  if (feature.stale) {
    const source = feature.stale.reason === "requirement_changed" ? "requirement" : "Epic";
    return {
      ok: false,
      reason: `Reconcile the stale Feature because its source ${source} changed before changing Stories.`,
    };
  }
  if (feature.status !== "approved") {
    return { ok: false, reason: "Approve the Feature before generating its Stories." };
  }
  return { ok: true };
}

export function storyRegenerationLoss(story: Story): string | null {
  if (story.status === "generated") return null;
  return `This Story has been ${story.status}. Regenerating replaces its content, its acceptance criteria and human review state.`;
}
