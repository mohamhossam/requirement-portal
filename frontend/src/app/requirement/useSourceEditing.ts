import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { api, type Requirement, type RequirementImpact, type RequirementInput } from "../../api/client";
import type { AttachmentState } from "../../features/documents/DocumentPanel";
import type { WorkspaceChange } from "../workspaceInvalidation";

/**
 * Editing the source requirement, which the source rail and the capture stage
 * both reach into: capture hides its own attachment panel while the rail's form
 * is open, and both report attachment readiness.
 *
 * A save that would invalidate downstream work goes through an impact preview
 * first, and only commits once that has been acknowledged.
 */
export function useSourceEditing({
  id,
  requirement,
  refresh,
}: {
  id: string;
  requirement: Requirement | undefined;
  refresh: (change: WorkspaceChange) => Promise<unknown>;
}) {
  const [editing, setEditing] = useState(false);
  const [attachments, setAttachments] = useState<AttachmentState>({
    hasIncludedAttachment: false,
    busy: false,
    blocked: false,
  });
  const [pending, setPending] = useState<RequirementInput | null>(null);
  const [impact, setImpact] = useState<RequirementImpact | null>(null);

  const update = useMutation({
    meta: { action: "Saving the requirement" },
    mutationFn: ({ input, acknowledged }: { input: RequirementInput; acknowledged: boolean }) =>
      api.updateRequirement(id, {
        ...input,
        expected_version: requirement?.version,
        impact_acknowledged: acknowledged,
      }),
    onSuccess: async () => {
      setEditing(false);
      await refresh("source");
    },
  });

  const preview = useMutation({
    meta: { action: "Checking the impact of this edit" },
    mutationFn: (input: RequirementInput) =>
      api.previewRequirementImpact(id, { ...input, expected_version: requirement!.version }),
    onSuccess: (result, input) => {
      if (result.requires_acknowledgement) {
        setPending(input);
        setImpact(result);
      } else {
        update.mutate({ input, acknowledged: false });
      }
    },
  });

  const dismissImpact = () => {
    setPending(null);
    setImpact(null);
  };

  return {
    editing,
    setEditing,
    attachments,
    setAttachments,
    pending,
    impact,
    dismissImpact,
    commitAcknowledged: () => {
      const input = pending;
      dismissImpact();
      if (input) update.mutate({ input, acknowledged: true });
    },
    submit: (input: RequirementInput) => preview.mutate(input),
    busy: update.isPending || preview.isPending,
    error: update.error ?? preview.error ?? null,
  };
}

export type SourceEditing = ReturnType<typeof useSourceEditing>;
