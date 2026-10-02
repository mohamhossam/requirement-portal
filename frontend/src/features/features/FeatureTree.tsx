import type { FeatureInput, FeatureSet } from "../../api/client";
import { FeatureCard } from "./FeatureCard";

export function FeatureTree({ requirementId, featureSet, busyFeatureId, errors, canManage, onEdit, onApprove }: {
  requirementId: string;
  featureSet: FeatureSet;
  busyFeatureId: string | null;
  errors: Record<string, string | null>;
  canManage: boolean;
  onEdit: (featureId: string, input: FeatureInput, expectedVersion: number) => Promise<unknown> | void;
  onApprove: (featureId: string) => void;
}) {
  return (
    <div className="grid gap-4">
      {featureSet.features.map((feature, index) => (
        <FeatureCard
          key={feature.id}
          requirementId={requirementId}
          feature={feature}
          position={index + 1}
          busy={busyFeatureId === feature.id}
          error={errors[feature.id] ?? null}
          canManage={canManage}
          onEdit={(input, expectedVersion) => onEdit(feature.id, input, expectedVersion)}
          onApprove={() => onApprove(feature.id)}
        />
      ))}
    </div>
  );
}
