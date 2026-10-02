import { useQuery } from "@tanstack/react-query";
import { memo } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Link } from "react-router-dom";

import { api, type Epic, type Feature } from "../../api/client";
import { Skeleton } from "../../components/Skeleton";
import { cx } from "../../components/ui/cx";
import { HOVER_GROUND, TRANSITION } from "../../components/ui/recipes";
import { storyGist } from "../../features/stories/storyVoice";
import { VerdictText } from "../../features/breakdown/BacklogStatus";
import { backlogVerdict } from "../../features/breakdown/labels";
import { queryKeys } from "../queryKeys";

/**
 * The Epic → Feature → Story tree, as depth inside the Backlog step.
 *
 * It answers in StageRail's words on purpose: the same 3px left edge, the same
 * `--accent-wash` ground for the thing you are looking at, the same 44px rows,
 * the same hover. One spine, two scales — the journey above, the backlog
 * beneath it — so a person reads "where am I in this requirement" and "where am
 * I in its backlog" as one question. It used to be a third column in a second
 * type register with its own red (`#b52e2e`), which is the "Backlog is a
 * different application" cost docs/ux-plan.md §3.3 records.
 *
 * Presentation only: the Stories query below is the one that was already here,
 * unchanged, still gated on the branch being open.
 *
 * Phase 4: each row carries its verdict — Needs approval, Out of date,
 * Approved — with a glyph, not the provenance it used to print; and the row you
 * are viewing is marked the way StageRail marks a viewed step (weight and an
 * inset ring), so the accent is not spent a second time beside the journey's
 * current step.
 */

/** A row. `depth` is the indent step, not a heading level. */
function rowClass(current: boolean) {
  return cx(
    // `border-0` before the left edge: preflight is not imported, so
    // `border-solid` alone would leave the other three sides at the UA's
    // `medium` width in `currentColor`.
    "grid min-h-11 content-center gap-0.5 rounded-sm border-0 border-l-[3px] border-solid",
    "px-3 py-2 no-underline",
    TRANSITION,
    "text-ink border-l-transparent",
    current ? "font-semibold [box-shadow:inset_0_0_0_1px_var(--line-strong)]" : HOVER_GROUND,
  );
}

function RowLabel({
  children,
  clamp = 1,
  title,
}: {
  children: React.ReactNode;
  clamp?: 1 | 2;
  /** The untruncated text, for a hover and for anyone reading the markup. */
  title?: string;
}) {
  return (
    // `min-w-0` so the clamp actually clamps instead of widening the rail.
    <span
      title={title}
      className={cx(
        "text-body min-w-0 [overflow-wrap:anywhere]",
        clamp === 1 ? "truncate" : "line-clamp-2",
      )}
    >
      {children}
    </span>
  );
}

function RowStatus({ item, level }: { item: Parameters<typeof backlogVerdict>[0]; level: "epic" | "feature" | "story" }) {
  return <VerdictText verdict={backlogVerdict(item, level)} />;
}

function FeatureBranch({
  requirementId,
  feature,
  selectedFeatureId,
  selectedStoryId,
  expanded,
  onExpand,
  onSelect,
}: {
  requirementId: string;
  feature: Feature;
  selectedFeatureId?: string;
  selectedStoryId?: string;
  expanded: boolean;
  onExpand: () => void;
  onSelect: () => void;
}) {
  const stories = useQuery({
    queryKey: queryKeys.stories(requirementId, feature.id),
    queryFn: () => api.getStories(requirementId, feature.id),
    enabled: expanded || selectedFeatureId === feature.id,
  });
  const path = `/requirements/${requirementId}/breakdown/features/${feature.id}`;
  const current = selectedFeatureId === feature.id && !selectedStoryId;

  return (
    <li>
      <div className="flex items-stretch">
        <button
          type="button"
          aria-expanded={expanded}
          aria-label={`${expanded ? "Collapse" : "Expand"} ${feature.name}`}
          onClick={onExpand}
          className={cx(
            "text-ink-muted hover:text-ink grid min-h-11 w-7 shrink-0 cursor-pointer",
            "place-items-center rounded-sm border-0 bg-transparent",
            TRANSITION,
          )}
        >
          {expanded ? (
            <ChevronDown aria-hidden="true" size={15} />
          ) : (
            <ChevronRight aria-hidden="true" size={15} />
          )}
        </button>
        <Link
          to={path}
          aria-current={current ? "page" : undefined}
          onClick={onSelect}
          className={cx(rowClass(current), "min-w-0 flex-1")}
        >
          {/* The full name on hover: two Features sharing a long prefix
              truncated to the same words. */}
          <RowLabel title={feature.name}>{feature.name}</RowLabel>
          <RowStatus item={feature} level="feature" />
        </Link>
      </div>

      {expanded && (
        // The hairline is the nesting cue; the indent alone reads as drift.
        <ul className="border-line animate-branch-unfold m-0 ml-3.5 list-none border-0 border-l border-solid p-0 pl-1.5 motion-reduce:animate-none">
          {stories.isPending ? (
            <li className="px-3 py-2">
              <Skeleton label={`Loading Stories for ${feature.name}`} variant="inline" />
            </li>
          ) : stories.isError ? (
            <li className="text-danger text-meta px-3 py-2">Stories could not be loaded.</li>
          ) : !stories.data?.stories.length ? (
            <li className="text-ink-muted text-meta px-3 py-2">No Stories yet</li>
          ) : (
            stories.data.stories.map((story) => {
              const active = selectedStoryId === story.id && selectedFeatureId === feature.id;
              return (
                <li key={story.id}>
                  <Link
                    to={`${path}/stories/${story.id}`}
                    aria-current={active ? "page" : undefined}
                    onClick={onSelect}
                    className={rowClass(active)}
                  >
                    <RowLabel clamp={2} title={story.voice}>{storyGist(story.voice)}</RowLabel>
                    <RowStatus item={story} level="story" />
                  </Link>
                </li>
              );
            })
          )}
        </ul>
      )}
    </li>
  );
}

function BacklogTreeImpl({
  requirementId,
  epic,
  features,
  selectedFeatureId,
  selectedStoryId,
  expanded,
  onExpand,
  onSelect,
}: {
  requirementId: string;
  epic: Epic | null;
  features: Feature[];
  selectedFeatureId?: string;
  selectedStoryId?: string;
  expanded: Record<string, boolean>;
  onExpand: (featureId: string) => void;
  onSelect: () => void;
}) {
  const base = `/requirements/${requirementId}/breakdown`;
  const onEpic = !selectedFeatureId;
  // `aria-current` still marks the route; the accent ground does not, because
  // until an Epic is generated the row names something that does not exist.
  const epicMarked = onEpic && Boolean(epic);

  return (
    // `ml-3` and the hairline: the tree is subordinate to the Backlog step
    // above it, and has to be seen to be. Flush left it read as six journey
    // steps followed by more journey steps.
    <nav
      aria-label="Backlog items"
      className="border-line ml-3 grid gap-1 border-0 border-l border-solid pl-2"
    >
      {/* Named for assistive technology only: in the rail, step 5 immediately
          above this already reads "Backlog", and in the drawer the dialog title
          does. */}
      <h2 className="sr-only">Backlog</h2>
      <ul className="m-0 grid list-none gap-0.5 p-0">
        <li>
          <Link
            to={`${base}/epic`}
            aria-current={onEpic ? "page" : undefined}
            onClick={onSelect}
            className={rowClass(epicMarked)}
          >
            <RowLabel title={epic?.name}>{epic?.name ?? "Epic"}</RowLabel>
            {epic && <RowStatus item={epic} level="epic" />}
          </Link>
        </li>
        {features.map((feature) => (
          <FeatureBranch
            key={feature.id}
            requirementId={requirementId}
            feature={feature}
            selectedFeatureId={selectedFeatureId}
            selectedStoryId={selectedStoryId}
            expanded={expanded[feature.id] ?? selectedFeatureId === feature.id}
            onExpand={() => onExpand(feature.id)}
            onSelect={onSelect}
          />
        ))}
      </ul>
    </nav>
  );
}

/**
 * Memoised because this tree is mounted twice — once in the rail, once in the
 * drawer — and each `FeatureBranch` inside it holds a query subscription. Its
 * props are stabilised by the workspace above it, so a render of the Story card
 * beside it no longer walks the whole backlog.
 */
export const BacklogTree = memo(BacklogTreeImpl);
