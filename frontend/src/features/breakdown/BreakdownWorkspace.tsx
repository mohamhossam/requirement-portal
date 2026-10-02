import { useCallback, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import type { Epic, Feature, FeatureSet, RequirementAnalysis } from "../../api/client";
import { BacklogTree } from "../../app/requirement/BacklogTree";
import { RailSlot } from "../../app/requirement/RailSlot";
import { EmptyState } from "../../components/EmptyState";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Skeleton } from "../../components/Skeleton";
import { WorkspaceDrawer } from "../../components/WorkspaceDrawer";
import { Button, ButtonLink, Card, CardHeader, cx } from "../../components/ui";
import { HOVER_GROUND_SOFT, TRANSITION } from "../../components/ui/recipes";
import { canDecompose, canGenerateEpic } from "../../review/rules";
import { DropBadge } from "../features/DropBadge";
import { EpicCard } from "../epic/EpicCard";
import { FeatureCard } from "../features/FeatureCard";
import { StoryList } from "../stories/StoryList";
import { VerdictText } from "./BacklogStatus";
import { backlogVerdict, needsApproval, signature } from "./labels";

type Props = {
  requirementId: string; epic: Epic | null; features: FeatureSet | null; analysis: RequirementAnalysis | null;
  epicLoading: boolean; featuresLoading: boolean; epicError: string | null; featuresError: string | null;
  canManage: boolean; epicBusy: boolean; featureBusy: boolean; busyFeatureId: string | null;
  featureErrors: Record<string, string | null>;
  onEditEpic: Parameters<typeof EpicCard>[0]["onEdit"]; onApproveEpic: () => void; onGenerateEpic: (force: boolean) => void;
  onEditFeature: (id: string, ...args: Parameters<Parameters<typeof FeatureCard>[0]["onEdit"]>) => Promise<unknown> | void;
  onApproveFeature: (id: string) => void; onGenerateFeatures: () => void;
  onMapArchitecture: () => void; architectureBusy: boolean; architectureError: string | null;
};

/**
 * One Feature on the Epic page. A row, not a card: these are siblings in a list
 * of five to fifteen, and a card apiece turns a scannable list into a stack of
 * boxes with nothing to scan down.
 */
function FeatureRow({ base, feature }: { base: string; feature: Feature }) {
  return (
    <li className="[&+li]:border-line [&+li]:border-0 [&+li]:border-t [&+li]:border-solid">
      <Link
        to={`${base}/features/${feature.id}`}
        className={cx(
          "text-ink -mx-3 flex flex-wrap items-center gap-3 rounded-sm px-3 py-4 no-underline",
          HOVER_GROUND_SOFT,
          TRANSITION,
        )}
      >
        <span className="grid min-w-0 flex-1 gap-0.5">
          <span className="text-title [overflow-wrap:anywhere]">{feature.name}</span>
          {signature(feature) && <span className="text-meta text-ink-muted tabular-nums">{signature(feature)}</span>}
        </span>
        <DropBadge drop={feature.delivery_drop} />
        {/* The verdict, not the provenance: "Edited" after an approval meant
            "your sign-off lapsed", and read as nothing at all. */}
        <VerdictText verdict={backlogVerdict(feature, "feature")} />
      </Link>
    </li>
  );
}

export function BreakdownWorkspace(props: Props) {
  const { featureId, storyId } = useParams();
  const navigate = useNavigate();
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const { requirementId, epic, features, analysis, canManage } = props;
  const items = useMemo(() => features?.features ?? [], [features]);
  const selected = items.find((item) => item.id === featureId);
  const base = `/requirements/${requirementId}/breakdown`;
  const generation = canGenerateEpic(analysis), decomposition = canDecompose(analysis, epic);
  const owed = items.filter(needsApproval);
  const nextOwed = owed[0];
  /**
   * Why generating is allowed, in the person's own words. The rail can legibly
   * show Clarify as the current step while this is true — the analysis was
   * confirmed and questions stayed open — and with nothing saying so, the
   * loudest control on the screen answered "may I proceed?" with yes while the
   * rail answered no.
   */
  const confirmedOn = analysis?.confirmed_at
    ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(analysis.confirmed_at))
    : null;
  const epicEmptyMessage = !generation.ok
    ? generation.reason
    : confirmedOn
      ? `Generate an Epic from the analysis confirmed on ${confirmedOn}.`
      : "Generate an Epic from the confirmed analysis.";
  const clear = useCallback(() => { setDrawerOpen(false); setNotice(null); }, []);
  // `featureId` stays a dependency on purpose: an unrecorded branch defaults to
  // open when it is the Feature being viewed, which is what the row renders, so
  // the toggle has to start from the same value or the first click is a no-op.
  const handleExpand = useCallback(
    (id: string) =>
      setExpanded((current) => ({ ...current, [id]: !(current[id] ?? featureId === id) })),
    [featureId],
  );

  const tree = (
    <BacklogTree
      requirementId={requirementId}
      epic={epic}
      features={items}
      selectedFeatureId={featureId}
      selectedStoryId={storyId}
      expanded={expanded}
      onExpand={handleExpand}
      onSelect={clear}
    />
  );

  return (
    <>
      {/* The tree lives in the requirement's own rail from `lg` up — one spine,
          the journey above it, its depth below. Under `lg` the rail is a
          scrolling row of steps with no room for depth, so the tree moves into
          the drawer the Source and People panels already use. */}
      <RailSlot>
        <div className="hidden lg:block">{tree}</div>
      </RailSlot>
      {drawerOpen && (
        <WorkspaceDrawer title="Browse backlog" onClose={() => setDrawerOpen(false)}>
          {tree}
        </WorkspaceDrawer>
      )}

      <div className="backlog-detail grid min-w-0 gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          {/* A breadcrumb of one crumb is not a trail, it is an eyebrow over
              the card below it. On the Epic route the rail already says where
              you are, so there is nothing left for it to add. */}
          <nav aria-label="Breadcrumb" className="backlog-breadcrumbs min-w-0" hidden={!featureId}>
            <ol className="text-meta text-ink-muted m-0 flex list-none flex-wrap items-center gap-1.5 p-0">
              <li className="min-w-0">
                {featureId ? (
                  <Link to={`${base}/epic`} className="text-ink-muted hover:text-accent inline-flex min-h-6 items-center no-underline">Epic</Link>
                ) : (
                  <span aria-current="page" className="text-ink font-semibold">Epic</span>
                )}
              </li>
              {selected && (
                <>
                  {/* The separator is punctuation, not a step: read aloud it is
                      just "slash" between two names. */}
                  <li aria-hidden="true" className="text-ink-faint">/</li>
                  <li className="min-w-0">
                    {storyId ? (
                      <Link to={`${base}/features/${selected.id}`} className="text-ink-muted hover:text-accent inline-flex min-h-6 items-center no-underline">
                        {selected.name}
                      </Link>
                    ) : (
                      <span aria-current="page" className="text-ink font-semibold">{selected.name}</span>
                    )}
                  </li>
                  {storyId && (
                    <>
                      <li aria-hidden="true" className="text-ink-faint">/</li>
                      <li><span aria-current="page" className="text-ink font-semibold">Story</span></li>
                    </>
                  )}
                </>
              )}
            </ol>
          </nav>
          <Button className="lg:hidden" aria-haspopup="dialog" onClick={() => setDrawerOpen(true)}>Browse backlog</Button>
        </div>

        {notice && (
          <p
            className="border-line bg-accent-wash text-body text-ink-soft m-0 rounded-md border border-solid border-l-[3px] border-l-[var(--accent)] px-3 py-2"
            role="status"
          >
            {notice}
          </p>
        )}

        {props.epicLoading ? <Skeleton label="Loading the Epic" /> : props.epicError && !epic ? <ErrorNotice message={props.epicError} /> : featureId && props.featuresLoading ? <Skeleton label="Loading Features" /> : featureId && props.featuresError ? <ErrorNotice message={props.featuresError} /> : featureId && !selected ? <EmptyState title="Feature not found" message="This Feature is not in the current backlog." action={<ButtonLink to={`${base}/epic`}>Return to Epic</ButtonLink>} /> : null}

        <div hidden={Boolean(featureId) || props.epicLoading} className="grid gap-4">
          {epic ? (
            <EpicCard epic={epic} analysis={analysis} features={features} canManage={canManage} focused busy={props.epicBusy} error={props.epicError} onEdit={props.onEditEpic} onApprove={props.onApproveEpic} onRegenerate={props.onGenerateEpic} />
          ) : (
            !props.epicError && !props.epicLoading && (
              <EmptyState
                title="No Epic yet"
                message={epicEmptyMessage}
                action={
                  <Button
                    variant="primary"
                    loading={props.epicBusy}
                    loadingLabel="Generating…"
                    disabled={!canManage || !generation.ok}
                    onClick={() => props.onGenerateEpic(false)}
                  >
                    Generate Epic
                  </Button>
                }
              />
            )
          )}

          {epic && (
            <Card as="section" className="backlog-child-list" aria-labelledby="backlog-features-title">
              <CardHeader
                headingLevel="h2"
                title={<span id="backlog-features-title">Features{features ? ` (${items.length})` : ""}</span>}
                // "What needs me?", answered from the list itself.
                description={items.length > 0
                  ? owed.length
                    ? `${owed.length} of ${items.length} need${owed.length === 1 ? "s" : ""} approval`
                    : "Every Feature is approved"
                  : undefined}
                actions={items.length > 0 && (
                  // Named after where it goes. "Continue reviewing" meant the
                  // next unapproved Feature here and Review & approve on a
                  // Story, and said neither.
                  nextOwed ? (
                    // The name is in the row below and on hover; in the label it
                    // made the one filled button the widest thing on the page.
                    <ButtonLink
                      variant={epic.status === "approved" && !epic.stale ? "primary" : "secondary"}
                      to={`${base}/features/${nextOwed.id}`}
                      title={nextOwed.name}
                    >
                      Review next Feature
                    </ButtonLink>
                  ) : (
                    <ButtonLink to={`/requirements/${requirementId}/review`}>Go to Review &amp; approve</ButtonLink>
                  )
                )}
              />
              {props.featuresLoading ? <Skeleton label="Loading Features" /> : props.featuresError ? <ErrorNotice message={props.featuresError} /> : items.length ? (
                <ul className="m-0 list-none p-0">
                  {items.map((feature) => <FeatureRow key={feature.id} base={base} feature={feature} />)}
                </ul>
              ) : (
                <EmptyState
                  title="No Features yet"
                  message={decomposition.ok ? "Generate the capabilities that deliver this Epic." : decomposition.reason}
                  action={
                    <Button
                      variant="primary"
                      loading={props.featureBusy}
                      loadingLabel="Generating…"
                      disabled={!canManage || !decomposition.ok}
                      onClick={props.onGenerateFeatures}
                    >
                      Decompose into Features
                    </Button>
                  }
                />
              )}
            </Card>
          )}
        </div>

        {items.map((feature, index) => (
          <div key={feature.id} hidden={featureId !== feature.id} className="grid gap-4">
            <div hidden={Boolean(storyId)} className="grid gap-4">
              <FeatureCard requirementId={requirementId} feature={feature} position={index + 1} canManage={canManage} focused busy={props.busyFeatureId === feature.id} error={props.featureErrors[feature.id] ?? null} onEdit={(...args) => props.onEditFeature(feature.id, ...args)} onApprove={() => props.onApproveFeature(feature.id)}
                onMapArchitecture={props.onMapArchitecture} architectureBusy={props.architectureBusy} architectureError={props.architectureError} />
            </div>
            <StoryList requirementId={requirementId} feature={feature} canManage={canManage} focused visible={featureId === feature.id} expanded={expanded[feature.id] ?? false} selectedStoryId={featureId === feature.id ? storyId : undefined}
              nextFeature={items[index + 1] ? { id: items[index + 1]!.id, name: items[index + 1]!.name } : undefined}
              onStoryRemoved={() => { setNotice("The Story set changed. Review the updated Stories below."); navigate(`${base}/features/${feature.id}`, { replace: true }); }} />
          </div>
        ))}
      </div>
    </>
  );
}
