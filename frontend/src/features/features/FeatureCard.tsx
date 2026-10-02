import { useState } from "react";

import type { Feature, FeatureInput } from "../../api/client";
import { EditorConflictNotice } from "../../components/EditorConflictNotice";
import { ErrorNotice } from "../../components/ErrorNotice";
import { ProvenanceDetails } from "../../components/ProvenanceDetails";
import { StalenessNotice } from "../../components/StalenessNotice";
import { Disclosure } from "../../components/Disclosure";
import { Badge, Button, Card, CardHeader } from "../../components/ui";
import { canApprove } from "../../review/rules";
import { ArchitectureImpactPanel } from "../architecture/ArchitectureImpactPanel";
import { StoryList } from "../stories/StoryList";
import { DropBadge } from "./DropBadge";
import { PATTERN_LABEL } from "./splittingPatterns";
import { FeatureEditForm } from "./FeatureEditForm";
import { BacklogStatus } from "../breakdown/BacklogStatus";
import { useEditFocus } from "../breakdown/useEditFocus";

/**
 * One Feature — a customer-recognizable capability.
 *
 * The rotated number in a tinted gutter is gone. Features are approved
 * independently and ordered by delivery drop, so "03" down the left edge dressed
 * an unordered set as a sequence and spent 3rem of a column that the rail was
 * already competing for. `delivery_drop` carries the ordering information that
 * is actually true, as a badge, beside the status.
 */
export function FeatureCard({
  requirementId, feature, busy, error, canManage, onEdit, onApprove, focused = false,
  onMapArchitecture, architectureBusy = false, architectureError = null,
}: {
  focused?: boolean;
  /**
   * Map or refresh the requirement's architecture. It lived in a disclosure of
   * its own under the card, apart from the "System impact" it produces; it is
   * inside that disclosure now, beside its result.
   */
  onMapArchitecture?: () => void;
  architectureBusy?: boolean;
  architectureError?: string | null;
  requirementId: string;
  feature: Feature;
  /** Kept for the non-focused tree; the card no longer renders an ordinal. */
  position: number;
  busy: boolean;
  error: string | null;
  canManage: boolean;
  onEdit: (input: FeatureInput, expectedVersion: number) => Promise<unknown> | void;
  onApprove: () => void;
}) {
  const [editing, setEditing] = useState<Feature | null>(null);
  const approval = canApprove(feature);
  const { trigger, form } = useEditFocus(Boolean(editing));

  if (editing) {
    return <div ref={form}><EditorConflictNotice baselineVersion={editing.version} currentVersion={feature.version} currentContent={[feature.name, feature.outcome, feature.splitting_rationale].join("\n\n")} onReconcile={() => setEditing(feature)} /><FeatureEditForm feature={editing} busy={busy} error={error} onCancel={() => setEditing(null)} onSave={async (input) => { try { await onEdit(input, editing.version); setEditing(null); } catch { /* Mutation error remains visible with the draft. */ } }} /></div>;
  }

  const approveReason = !approval.ok ? approval.reason : undefined;
  const impact = feature.architecture;

  return (
    <Card
      as="article"
      className="feature-card"
      id={`feature-${feature.id}`}
      tone={feature.stale ? "warning" : "default"}
    >
      <CardHeader
        headingLevel="h2"
        title={feature.name}
        actions={
          <>
            <Button ref={trigger} disabled={!canManage || busy} onClick={() => setEditing(feature)}>Edit</Button>
            {(!focused || feature.status !== "approved") && (
              <Button
                variant="primary"
                disabled={!canManage || busy}
                blockedReason={approveReason}
                onClick={onApprove}
              >
                {feature.status === "approved" ? "Approved" : "Approve"}
              </Button>
            )}
          </>
        }
      />

      <div className="mb-4 grid gap-2">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <BacklogStatus item={feature} level="feature" />
          <DropBadge drop={feature.delivery_drop} />
        </div>
        {/* Which systems this touches, on the card: the architect's first
            question was two collapsed disclosures deep. */}
        <p className="text-meta text-ink-muted m-0 flex flex-wrap items-center gap-2">
          {impact ? (
            <>
              <span>
                {impact.systems.length
                  ? `Touches ${impact.systems.map((system) => system.name).join(", ")}`
                  : "No likely systems identified"}
              </span>
              {impact.cross_system && <Badge tone="warning">Crosses systems</Badge>}
            </>
          ) : (
            <span>Systems not mapped yet</span>
          )}
        </p>
        {canManage && approval.ok && (
          <p className="text-meta text-ink-muted m-0 max-w-[var(--measure-document)]">
            Approving signs off this Feature as it reads now, so its Stories can be generated. Any later edit needs a new approval; Stories are approved on Review &amp; approve.
          </p>
        )}
      </div>

      {focused && !canManage && (
        <p className="text-ink-muted text-meta m-0 mb-3">
          You do not have permission to change this Requirement.
        </p>
      )}
      {feature.stale && <StalenessNotice stale={feature.stale} />}
      {error && <ErrorNotice message={error} />}

      <div className="grid gap-1">
        <span className="text-label text-ink-muted">Outcome</span>
        <p className="text-document font-document text-ink-soft m-0 max-w-[var(--measure-document)]">
          {feature.outcome}
        </p>
      </div>

      {focused ? (
        <>
          <Disclosure label="Splitting rationale">
            <div className="grid gap-2">
              <Badge tone="neutral">{PATTERN_LABEL[feature.splitting_pattern]}</Badge>
              <p className="text-document font-document text-ink-soft m-0 max-w-[var(--measure-document)]">
                {feature.splitting_rationale}
              </p>
            </div>
          </Disclosure>
          <Disclosure label="System impact">
            <div className="grid gap-3">
              <ArchitectureImpactPanel impact={feature.architecture} />
              {onMapArchitecture && (
                <div>
                  <Button
                    loading={architectureBusy}
                    loadingLabel="Mapping…"
                    disabled={!canManage}
                    onClick={onMapArchitecture}
                  >
                    {feature.architecture ? "Refresh architecture" : "Map architecture"}
                  </Button>
                </div>
              )}
              {architectureError && <ErrorNotice message={architectureError} />}
            </div>
          </Disclosure>
        </>
      ) : (
        <>
          <div className="mt-5 grid gap-1">
            <span className="text-label text-ink-muted">Split by</span>
            <p className="text-body text-ink-soft m-0">{PATTERN_LABEL[feature.splitting_pattern]}</p>
          </div>
          <div className="mt-5 grid gap-1">
            <span className="text-label text-ink-muted">Why separate</span>
            <p className="text-document font-document text-ink-soft m-0 max-w-[var(--measure-document)]">
              {feature.splitting_rationale}
            </p>
          </div>
          <ArchitectureImpactPanel impact={feature.architecture} />
        </>
      )}

      <ProvenanceDetails provenance={feature.provenance} />

      {!focused && (
        <div className="border-line mt-5 border-0 border-t border-solid pt-4">
          <span className="text-label text-ink-muted">Sprint-sized Stories</span>
          <StoryList requirementId={requirementId} feature={feature} canManage={canManage} />
        </div>
      )}
    </Card>
  );
}
