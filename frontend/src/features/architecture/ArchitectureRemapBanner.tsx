import { useQuery } from "@tanstack/react-query";
import { TriangleAlert } from "lucide-react";
import { useState } from "react";

import { knowledgeApi } from "../../api/knowledge";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { Button, Card } from "../../components/ui";

/**
 * Says when a breakdown was mapped with a catalogue version no longer in use,
 * and lets the requirement's own team remap it. People without a knowledge
 * role cannot read the version in use, so they are not shown the banner.
 */
export function ArchitectureRemapBanner({ mappedWith, canRemap, busy, onRemap }: {
  /** The catalogue versions the breakdown's current mappings were made with. */
  mappedWith: string[];
  canRemap: boolean;
  busy: boolean;
  onRemap: () => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const active = useQuery({ queryKey: ["knowledge", "active"], queryFn: knowledgeApi.active,
    enabled: mappedWith.length > 0, retry: false });
  const catalogue = active.data;
  if (!catalogue || !mappedWith.some((version) => version !== catalogue.id)) return null;
  return (
    <>
      <Card as="section" inset aria-labelledby="remap-title" className="flex flex-wrap items-start gap-4">
        <TriangleAlert aria-hidden="true" className="text-warning mt-0.5 shrink-0" size={20} />
        <div className="grid min-w-0 flex-1 gap-1">
          <h2 className="text-title text-ink m-0" id="remap-title">Mapped with an older architecture catalogue</h2>
          <p className="text-body text-ink-soft m-0 max-w-[var(--measure-document)]">
            A newer version, “{catalogue.name ?? catalogue.id}”, is in use. Remap this breakdown to check its systems
            and dependencies against it. Remapping resets approvals.
          </p>
        </div>
        {canRemap && (
          <Button loading={busy} loadingLabel="Remapping…" onClick={() => setConfirming(true)}>
            Remap architecture
          </Button>
        )}
      </Card>
      {confirming && (
        <ConfirmDialog
          title="Remap the architecture?"
          message="Every feature and story is mapped again with the catalogue in use. Approvals on this breakdown are reset and need to be given again."
          confirmLabel="Remap"
          onCancel={() => setConfirming(false)}
          onConfirm={() => { setConfirming(false); onRemap(); }}
        />
      )}
    </>
  );
}
