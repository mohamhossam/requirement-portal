import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { api, type Feature, type StoryInput, type StoryProposal } from "../../api/client";
import { errorMessage, errorReference } from "../../api/errors";
import { queryKeys } from "../../app/queryKeys";
import { invalidateWorkspace, invalidateWorkspaceKeys } from "../../app/workspaceInvalidation";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { EmptyState } from "../../components/EmptyState";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Skeleton } from "../../components/Skeleton";
import { ChevronLeft } from "lucide-react";

import { Badge, Button, ButtonLink, Card, Checkbox, cx } from "../../components/ui";
import { HOVER_GROUND_SOFT, TRANSITION } from "../../components/ui/recipes";
import { canGenerateStories } from "../../review/rules";
import { useRequirementJobs } from "../jobs/useRequirementJobs";
import { ManualStoryChangeDialog } from "./ManualStoryChangeDialog";
import { StoryCard } from "./StoryCard";
import { StoryProposalPanel } from "./StoryProposalPanel";
import { storyGist } from "./storyVoice";
import { VerdictText } from "../breakdown/BacklogStatus";
import { backlogVerdict } from "../breakdown/labels";

function qualityIdempotencyKey(featureId: string, stories: NonNullable<Awaited<ReturnType<typeof api.getStories>>>["stories"]) {
  const source = JSON.stringify(stories.map((story) => [story.id, story.role, story.action, story.value, story.acceptance_criteria]));
  let hash = 2166136261;
  for (let index = 0; index < source.length; index += 1) {
    hash = Math.imul(hash ^ source.charCodeAt(index), 16777619);
  }
  return `quality-${featureId.slice(0, 80)}-${(hash >>> 0).toString(36)}`;
}

export function StoryList({ requirementId, feature, canManage, focused = false, visible = true, expanded = false, selectedStoryId, onStoryRemoved, nextFeature }: {
  focused?: boolean; visible?: boolean; expanded?: boolean; selectedStoryId?: string; onStoryRemoved?: () => void;
  /**
   * Where "Next" goes after this Feature's last Story. It went dead there, and
   * the only way on was the rail, or a "Continue reviewing" that left for
   * Review & approve with work still open here.
   */
  nextFeature?: { id: string; name: string };
  requirementId: string;
  feature: Feature;
  canManage: boolean;
}) {
  const queryClient = useQueryClient();
  const [selectMode, setSelectMode] = useState(false);
  const observedStory = useRef<string | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [confirmRegenerateAll, setConfirmRegenerateAll] = useState(false);
  const [manualChange, setManualChange] = useState<{
    operation: "split" | "merge";
    sources: string[];
  } | null>(null);
  const jobs = useRequirementJobs(requirementId);

  const stories = useQuery({
    queryKey: queryKeys.stories(requirementId, feature.id),
    queryFn: ({ signal }) => api.getStories(requirementId, feature.id, { signal }),
    refetchOnMount: "always",
    enabled: !focused || visible || expanded,
  });
  const proposals = useQuery({
    queryKey: queryKeys.storyProposals(requirementId, feature.id),
    queryFn: ({ signal }) => api.listStoryProposals(requirementId, feature.id, { signal }),
    refetchOnMount: "always",
    enabled: !focused || visible,
  });
  /**
   * Visibility still gates this, but the Story set no longer does: waiting for
   * `stories` to resolve made the quality assessment the fifth and last wave of
   * a deep link, and it is the thing the reviewer is here to read. A Feature
   * with no Stories now costs one request that returns nothing, which is the
   * cheaper side of the trade.
   */
  const quality = useQuery({
    queryKey: queryKeys.storyQuality(requirementId, feature.id),
    queryFn: ({ signal }) => api.getFeatureStoryQualityAssessment(requirementId, feature.id, { signal }),
    refetchOnMount: "always",
    enabled: !focused || visible,
  });
  useEffect(() => {
    if (!focused || !visible || !selectedStoryId) { observedStory.current = null; return; }
    if (stories.data?.stories.some((story) => story.id === selectedStoryId)) observedStory.current = selectedStoryId;
    else if (stories.isSuccess && observedStory.current === selectedStoryId) { observedStory.current = null; onStoryRemoved?.(); }
  }, [focused, visible, selectedStoryId, stories.data, stories.isSuccess, onStoryRemoved]);
  const evaluateQuality = useMutation({
    mutationFn: () =>
      jobs.startJob({
          operation: "evaluate_feature_quality",
          feature_id: feature.id,
          context_token: stories.data?.generation_context_token ?? "",
        },
        qualityIdempotencyKey(feature.id, stories.data?.stories ?? []),
      ),
  });

  const refresh = () => invalidateWorkspace(queryClient, requirementId, "stories", feature.id);

  const generate = useMutation({
    mutationFn: () => jobs.startJob({
      operation: "generate_stories",
      feature_id: feature.id,
      context_token: feature.story_context_token ?? "",
    }),
  });
  const regenerateAll = useMutation({
    mutationFn: (force: boolean) => jobs.startJob({
      operation: "regenerate_story_set",
      feature_id: feature.id,
      force,
      context_token: stories.data?.generation_context_token ?? "",
    }),
  });
  const editStory = useMutation({
    mutationFn: ({ storyId, input, expectedVersion }: {
      storyId: string; input: StoryInput; expectedVersion: number
    }) => {
      return api.editStory(
        requirementId, feature.id, storyId, { ...input, expected_version: expectedVersion }
      );
    },
    onError: () => invalidateWorkspaceKeys(queryClient, [queryKeys.stories(requirementId, feature.id)]),
    onSuccess: refresh,
  });
  const regenerateStory = useMutation({
    mutationFn: ({ storyId, force }: { storyId: string; force: boolean }) => {
      const current = stories.data!.stories.find((story) => story.id === storyId)!;
      return jobs.startJob({
        operation: "regenerate_story",
        feature_id: feature.id,
        story_id: storyId,
        force,
        context_token: current.story_context_token ?? "",
      });
    },
  });
  const manualSplit = useMutation({
    mutationFn: ({ storyId, replacements }: { storyId: string; replacements: StoryInput[] }) =>
      api.splitStory(
        requirementId,
        feature.id,
        storyId,
        replacements,
        stories.data?.set_version ?? 1,
      ),
    onSuccess: async () => {
      setManualChange(null);
      await refresh();
    },
  });
  const manualMerge = useMutation({
    mutationFn: ({ storyIds, replacement }: { storyIds: string[]; replacement: StoryInput }) =>
      api.mergeStories(
        requirementId,
        feature.id,
        storyIds,
        replacement,
        stories.data?.set_version ?? 1,
      ),
    onSuccess: async () => {
      setManualChange(null);
      setSelected([]);
      await refresh();
    },
  });
  const propose = useMutation({
    mutationFn: ({ operation, ids }: { operation: "split" | "merge"; ids: string[] }) =>
      jobs.startJob({
        operation: "propose_story_change",
        feature_id: feature.id,
        change_operation: operation,
        source_story_ids: ids,
        context_token: stories.data?.generation_context_token ?? "",
      }),
    onSuccess: async () => {
      setSelected([]);
    },
  });
  const applyProposal = useMutation({
    mutationFn: (proposal: StoryProposal) =>
      api.applyStoryProposal(
        requirementId,
        feature.id,
        proposal.id,
        proposal.version,
        stories.data?.set_version ?? 1,
      ),
    onSuccess: refresh,
  });
  const discardProposal = useMutation({
    mutationFn: (proposal: StoryProposal) =>
      api.discardStoryProposal(
        requirementId,
        feature.id,
        proposal.id,
        proposal.version,
        stories.data?.set_version ?? 1,
      ),
    onSuccess: refresh,
  });

  const toggleSelect = (storyId: string) =>
    setSelected((current) =>
      current.includes(storyId)
        ? current.filter((id) => id !== storyId)
        : [...current, storyId],
    );

  const busyStoryId = editStory.isPending
    ? editStory.variables?.storyId
    : regenerateStory.isPending
      ? regenerateStory.variables?.storyId
      : undefined;
  const storyError = editStory.error ?? regenerateStory.error;
  const storyErrorId = editStory.variables?.storyId ?? regenerateStory.variables?.storyId ?? "";
  const proposalData = proposals.data ?? [];
  const proposalBusy = applyProposal.isPending || discardProposal.isPending;
  const proposalError = applyProposal.error ?? discardProposal.error ?? propose.error;
  const manualError = manualSplit.error ?? manualMerge.error;
  const generation = canGenerateStories(feature);
  /**
   * How many INVEST checks a Story failed, or null when the assessment is
   * stale or absent. The Story list used to show provenance alone, so two
   * Stories reading "Generated" could differ by two failed checks and a split
   * recommendation — the reviewer's actual question ("what needs me?") was
   * answerable only by opening every Story in turn. PRODUCT.md Principle 1:
   * never let a surface bury an unresolved thing to look finished.
   */
  const concerns = useMemo(() => {
    const map = new Map<string, number>();
    if (!quality.data?.fresh) return map;
    for (const item of quality.data.stories) {
      if (item.failure_count > 0) map.set(item.story_id, item.failure_count);
    }
    return map;
  }, [quality.data]);
  const affectsFeature = (id: string) => !jobs.targets[id]?.featureId || jobs.targets[id]?.featureId === feature.id;
  const storiesGenerating = generate.isPending || jobs.active.some((job) => job.operation === "generate_stories" && affectsFeature(job.id));
  const storiesRegenerating = regenerateAll.isPending || jobs.active.some((job) => job.operation === "regenerate_story_set" && affectsFeature(job.id));
  const qualityActive = jobs.active.some((job) => job.operation === "evaluate_feature_quality" && affectsFeature(job.id));

  /** Why a Story action is unavailable, in the person's own words. */
  const blocked = !canManage
    ? "You do not have permission to change this Requirement."
    : generation.ok ? null : generation.reason;

  if (stories.isError && !stories.data) return <div hidden={focused && !visible}><ErrorNotice message={errorMessage(stories.error)} reference={errorReference(stories.error)} /></div>;

  if (stories.isPending) return <div hidden={focused && !visible}><Skeleton label="Loading Stories" /></div>;

  const list = stories.data?.stories ?? [];
  const selectedStories = list.filter((story) => selected.includes(story.id));
  const selectedIndex = selectedStoryId ? list.findIndex((story) => story.id === selectedStoryId) : -1;
  const featureBase = `/requirements/${requirementId}/breakdown/features/${feature.id}`;
  const requestRegenerateAll = () => {
    if (list.some((story) => story.status !== "generated")) setConfirmRegenerateAll(true);
    else regenerateAll.mutate(false);
  };

  if (list.length === 0 && focused && selectedStoryId) return <div hidden={!visible}><EmptyState title="Story not found" message="This Story is not in the current Feature." action={<ButtonLink to={`/requirements/${requirementId}/breakdown/features/${feature.id}`}>Return to Feature</ButtonLink>} /></div>;

  if (list.length === 0) {
    return (
      <div className="grid gap-3" hidden={focused && !visible}>
        <EmptyState
          title="No Stories yet"
          message={
            generation.ok
              ? "Break this approved Feature into sprint-sized, testable User Stories."
              : generation.reason
          }
          action={
            <Button
              variant="primary"
              loading={storiesGenerating}
              loadingLabel="Generating…"
              disabled={!canManage || !generation.ok}
              onClick={() => generate.mutate()}
            >
              Generate Stories
            </Button>
          }
        />
        {generate.error && <ErrorNotice message={errorMessage(generate.error)} reference={errorReference(generate.error)} />}
      </div>
    );
  }

  return (
    <div className="grid gap-4" hidden={focused && !visible}>
      {stories.isError && <ErrorNotice message={errorMessage(stories.error)} reference={errorReference(stories.error)} />}

      {focused && selectedStoryId && selectedIndex >= 0 && (
        // The one filled action on a Story is the way forward through the
        // backlog: the next Story, then the next Feature, and only at the very
        // end Review & approve. It used to be "Continue reviewing", a filled
        // link out to Review & approve on every Story, whatever was left here.
        <nav
          aria-label="Story position"
          className="flex flex-wrap items-center justify-between gap-3"
        >
          <span className="text-meta text-ink-muted tabular-nums">
            Story {selectedIndex + 1} of {list.length}
          </span>
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            {selectedIndex > 0 ? (
              <ButtonLink
                to={`${featureBase}/stories/${list[selectedIndex - 1]!.id}`}
                icon={<ChevronLeft size={16} aria-hidden="true" />}
              >
                Previous
              </ButtonLink>
            ) : (
              // A real disabled button, not a link dimmed by opacity: that one
              // stayed reachable and activatable by keyboard, and measured 3.35:1.
              <Button disabled icon={<ChevronLeft size={16} aria-hidden="true" />}>Previous</Button>
            )}
            <ButtonLink to={featureBase}>All Stories</ButtonLink>
            {selectedIndex < list.length - 1 ? (
              <ButtonLink variant="primary" to={`${featureBase}/stories/${list[selectedIndex + 1]!.id}`}>
                Next Story
              </ButtonLink>
            ) : nextFeature ? (
              <ButtonLink
                variant="primary"
                title={nextFeature.name}
                to={`/requirements/${requirementId}/breakdown/features/${nextFeature.id}`}
              >
                Next Feature
              </ButtonLink>
            ) : (
              <ButtonLink variant="primary" to={`/requirements/${requirementId}/review`}>
                Go to Review &amp; approve
              </ButtonLink>
            )}
          </div>
        </nav>
      )}

      <div
        className="flex flex-wrap items-center justify-between gap-3"
        hidden={focused && Boolean(selectedStoryId)}
      >
        {/* A heading, so the list sits in the outline under the Feature. */}
        <h3 className="text-title text-ink m-0">
          {list.length} Stor{list.length === 1 ? "y" : "ies"}
        </h3>
        <div className="flex flex-wrap items-center gap-2">
          {focused && !selectedStoryId && list[0] && (
            <ButtonLink
              variant={feature.status === "approved" && !feature.stale ? "primary" : "secondary"}
              to={`/requirements/${requirementId}/breakdown/features/${feature.id}/stories/${list[0].id}`}
            >
              Review Stories
            </ButtonLink>
          )}
          {focused && (
            <Button onClick={() => { setSelectMode((mode) => !mode); setSelected([]); }}>
              {selectMode ? "Cancel selection" : "Select Stories"}
            </Button>
          )}
          {(!focused || selectMode) && (
            <>
              {/* Disabled, not gated: they wait on a selection of two, and the
                  one gate reason the list has is said once, on Regenerate all. */}
              <Button
                disabled={Boolean(blocked) || selected.length < 2 || manualMerge.isPending}
                onClick={() => setManualChange({ operation: "merge", sources: selected })}
              >
                Manual merge{selected.length >= 2 ? ` (${selected.length})` : ""}
              </Button>
              <Button
                disabled={Boolean(blocked) || selected.length < 2 || propose.isPending}
                loading={propose.isPending && propose.variables?.operation === "merge"}
                loadingLabel="Proposing…"
                onClick={() => propose.mutate({ operation: "merge", ids: selected })}
              >
                {`Propose merge${selected.length >= 2 ? ` (${selected.length})` : ""}`}
              </Button>
            </>
          )}
          {/* Gated, not disabled: the button keeps its tab stop and says why,
              instead of a reason floating on a line of its own. */}
          <Button
            blockedReason={blocked ?? undefined}
            loading={storiesRegenerating}
            loadingLabel="Regenerating…"
            onClick={requestRegenerateAll}
          >
            Regenerate all
          </Button>
        </div>
      </div>


      {regenerateAll.error && <ErrorNotice message={errorMessage(regenerateAll.error)} reference={errorReference(regenerateAll.error)} />}
      {proposals.error && <ErrorNotice message={errorMessage(proposals.error)} reference={errorReference(proposals.error)} />}
      {proposalError && <ErrorNotice message={errorMessage(proposalError)} reference={errorReference(proposalError)} />}
      {quality.error && (
        <ErrorNotice
          message={`Story quality could not be evaluated: ${errorMessage(quality.error)}`}
          reference={errorReference(quality.error)}
        />
      )}

      {quality.isPending && <Skeleton label="Loading the quality assessment" bars={2} />}
      {!quality.isPending && !quality.isError && (!quality.data || !quality.data.fresh) && (
        <Card tone="warning" role="status">
          <div className="flex flex-wrap items-center justify-between gap-3">
            {/* Two situations, each said as itself: never checked, or checked
                before the Stories changed. The old copy claimed the second
                whenever either was true. */}
            <p className="text-body text-ink-soft m-0">
              {quality.data
                ? "These Stories changed after they were checked, so the earlier findings no longer apply."
                : "These Stories have not been checked yet for whether they are ready to build."}
            </p>
            <Button
              loading={qualityActive || evaluateQuality.isPending}
              loadingLabel="Assessing quality…"
              disabled={!canManage}
              onClick={() => evaluateQuality.mutate()}
            >
              Check these Stories
            </Button>
          </div>
        </Card>
      )}
      {evaluateQuality.error && <ErrorNotice message={errorMessage(evaluateQuality.error)} reference={errorReference(evaluateQuality.error)} />}

      {proposalData.map((proposal) => (
        <StoryProposalPanel
          key={proposal.id}
          proposal={proposal}
          busy={!canManage || proposalBusy || !generation.ok}
          error={null}
          onApply={() => applyProposal.mutate(proposal)}
          onDiscard={() => discardProposal.mutate(proposal)}
        />
      ))}

      {focused && !selectedStoryId && (
        <ul className="compact-story-list border-line m-0 list-none rounded-md border border-solid p-0 px-4">
          {list.map((story) => (
            <li key={story.id} className="[&+li]:border-line [&+li]:border-0 [&+li]:border-t [&+li]:border-solid">
              {selectMode && (
                <div className="pt-3">
                  <Checkbox
                    label="Select to merge"
                    // Starts with the visible label (WCAG 2.5.3), then says which Story.
                    aria-label={`Select to merge: ${storyGist(story.voice)}`}
                    checked={selected.includes(story.id)}
                    disabled={!canManage || !generation.ok}
                    onChange={() => toggleSelect(story.id)}
                  />
                </div>
              )}
              <Link
                to={`/requirements/${requirementId}/breakdown/features/${feature.id}/stories/${story.id}`}
                className={cx(
                  "text-ink -mx-3 grid gap-1 rounded-sm px-3 py-4 no-underline",
                  HOVER_GROUND_SOFT,
                  TRANSITION,
                )}
              >
                <span
                  className="text-document font-document max-w-[var(--measure-document)]"
                  title={story.voice}
                >
                  {storyGist(story.voice)}
                </span>
                <span className="flex flex-wrap items-center gap-2">
                  <VerdictText verdict={backlogVerdict(story, "story")} />
                  {/* The count in words, never the colour alone (§4.5); and an
                      unchecked Story says so, rather than looking exactly like
                      one that was checked and passed. */}
                  {!quality.data?.fresh ? (
                    <span className="text-meta text-ink-muted">Not checked</span>
                  ) : concerns.get(story.id) ? (
                    <Badge tone="warning">{concerns.get(story.id)} to check</Badge>
                  ) : (
                    <span className="text-meta text-success">Ready to build</span>
                  )}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}

      {focused && selectedStoryId && !list.some((story) => story.id === selectedStoryId) && <EmptyState title="Story not found" message="This Story is not in the current Feature." action={<ButtonLink to={`/requirements/${requirementId}/breakdown/features/${feature.id}`}>Return to Feature</ButtonLink>} />}

      {list.map((story, index) => (
        <div key={story.id} hidden={focused && story.id !== selectedStoryId}>
        <StoryCard
          focused={focused}
          reviewHref={focused ? `/requirements/${requirementId}/review` : undefined}
          story={story}
          position={index + 1}
          busy={busyStoryId === story.id || jobs.active.some((job) => job.operation === "regenerate_story" && jobs.targets[job.id]?.storyId === story.id && affectsFeature(job.id))}
          error={storyErrorId === story.id && storyError ? errorMessage(storyError) : null}
          selected={selected.includes(story.id)}
          onToggleSelect={() => toggleSelect(story.id)}
          onEdit={(input, expectedVersion) => editStory.mutateAsync({ storyId: story.id, input, expectedVersion })}
          onRegenerate={(force) => regenerateStory.mutate({ storyId: story.id, force })}
          onSplit={() => propose.mutate({ operation: "split", ids: [story.id] })}
          onManualSplit={() =>
            setManualChange({ operation: "split", sources: [story.id] })
          }
          disabledReason={blocked}
          quality={quality.data?.fresh ? quality.data.stories.find((item) => item.story_id === story.id) ?? null : null}
        />
        </div>
      ))}

      {confirmRegenerateAll && (
        <ConfirmDialog
          title="Replace all Stories?"
          message="This Story set contains human-edited content. Regenerating replaces every Story, its acceptance criteria and its identity. Revision history keeps the previous set."
          confirmLabel="Replace all Stories"
          onCancel={() => setConfirmRegenerateAll(false)}
          onConfirm={() => {
            setConfirmRegenerateAll(false);
            regenerateAll.mutate(true);
          }}
        />
      )}
      {manualChange && (
        <ManualStoryChangeDialog
          operation={manualChange.operation}
          sources={list.filter((story) => manualChange.sources.includes(story.id))}
          busy={manualSplit.isPending || manualMerge.isPending}
          error={manualError ? errorMessage(manualError) : null}
          onCancel={() => setManualChange(null)}
          onSubmit={(drafts) => {
            if (manualChange.operation === "split") {
              manualSplit.mutate({ storyId: manualChange.sources[0]!, replacements: drafts });
            } else {
              manualMerge.mutate({
                storyIds: selectedStories.map((story) => story.id),
                replacement: drafts[0]!,
              });
            }
          }}
        />
      )}
    </div>
  );
}
