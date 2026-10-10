import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useDeferredValue, useState } from "react";
import { Link } from "react-router-dom";

import {
  api,
  type RequirementListParams,
  type SavedViewCriteria,
  type WorkflowStatus,
  type WorklistSort,
} from "../api/client";
import { errorMessage } from "../api/errors";
import { PageHeader } from "../components/shell";
import { AsyncState, asyncStatus } from "../components/states";
import { Button, ButtonLink } from "../components/ui/Button";
import { queryKeys } from "./queryKeys";
import { AttentionStrip } from "./dashboard/AttentionStrip";
import { stageLabels } from "./dashboard/labels";
import { SavedViewsMenu } from "./dashboard/SavedViewsMenu";
import { WorklistTable } from "./dashboard/WorklistTable";
import { WorklistToolbar } from "./dashboard/WorklistToolbar";
import { stagePath } from "./stagePath";
import { useDocumentTitle } from "./useDocumentTitle";
import { lastRequirementId } from "./lastRequirement";

const pageSize = 20;

export function DashboardPage() {
  useDocumentTitle("Requirements");
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search);
  const [statuses, setStatuses] = useState<WorkflowStatus[]>([]);
  const [sort, setSort] = useState<WorklistSort>("updated_desc");
  const [attentionOpen, setAttentionOpen] = useState(true);
  const [ownerId, setOwnerId] = useState("");
  const [assignedToMe, setAssignedToMe] = useState(false);
  const [selectedViewId, setSelectedViewId] = useState("");
  const [viewName, setViewName] = useState("");
  // Read once: RequirementPage and the intake page write it (docs/ux-plan.md §3.12).
  const [lastVisitedId] = useState(lastRequirementId);

  const baseParams: RequirementListParams = {
    q: deferredSearch,
    workflowStatus: statuses,
    sort,
    limit: pageSize,
    ownerId: ownerId || undefined,
    assignedToMe,
  };
  const requirements = useInfiniteQuery({
    queryKey: queryKeys.requirementList(baseParams),
    initialPageParam: 0,
    queryFn: ({ pageParam, signal }) => api.listRequirements({ ...baseParams, offset: pageParam }, { signal }),
    getNextPageParam: (page) => (page.has_more ? page.offset + page.requirements.length : undefined),
    refetchInterval: (query) =>
      query.state.data?.pages.some((page) =>
        page.requirements.some((item) => item.active_ai_operation !== null),
      )
        ? 2_000
        : false,
  });
  // Only the newest of each is offered, so only it is read.
  const drafts = useQuery({
    queryKey: queryKeys.requirementDrafts(),
    queryFn: ({ signal }) => api.listRequirementDrafts({ limit: 1 }, { signal }),
  });
  const legacyDrafts = useQuery({
    queryKey: queryKeys.scope("requirement-drafts", "unowned"),
    queryFn: ({ signal }) => api.listRequirementDrafts({ unowned: true, limit: 1 }, { signal }),
  });
  const savedViews = useQuery({ queryKey: queryKeys.savedViews(), queryFn: ({ signal }) => api.listSavedViews({ signal }) });
  const currentCriteria = (): SavedViewCriteria => ({
    query: search.trim() || null,
    workflow_statuses: statuses,
    sort,
    owner_id: ownerId || null,
    assigned_to_me: assignedToMe,
  });
  const createView = useMutation({
    mutationFn: () => api.createSavedView(viewName, currentCriteria()),
    onSuccess: async (view) => {
      setSelectedViewId(view.id);
      setViewName(view.name);
      await queryClient.invalidateQueries({ queryKey: queryKeys.savedViews() });
    },
  });
  const updateView = useMutation({
    mutationFn: () => {
      const view = savedViews.data?.find((item) => item.id === selectedViewId);
      if (!view) throw new Error("Choose a saved view first.");
      return api.updateSavedView(view.id, viewName, currentCriteria(), view.version);
    },
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: queryKeys.savedViews() }),
  });
  const deleteView = useMutation({
    mutationFn: () => {
      const view = savedViews.data?.find((item) => item.id === selectedViewId);
      if (!view) throw new Error("Choose a saved view first.");
      return api.deleteSavedView(view.id, view.version);
    },
    onSuccess: async () => {
      setSelectedViewId("");
      setViewName("");
      await queryClient.invalidateQueries({ queryKey: queryKeys.savedViews() });
    },
  });
  const claimDraft = useMutation({
    mutationFn: api.claimDraftOwnership,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.requirementDrafts() }),
        queryClient.invalidateQueries({ queryKey: queryKeys.scope("requirement-drafts", "unowned") }),
      ]);
    },
  });

  const firstPage = requirements.data?.pages[0];
  const list = requirements.data?.pages.flatMap((page) => page.requirements) ?? [];
  const counts = firstPage?.status_counts;
  const attention = firstPage?.attention ?? [];
  const latestDraft = drafts.data?.drafts[0];
  const firstLegacyDraft = legacyDrafts.data?.drafts[0];
  const hasFilters = Boolean(search || statuses.length || ownerId || assignedToMe);
  // Only from what the worklist already loaded: no extra request for a link.
  const lastVisited = lastVisitedId ? list.find((item) => item.id === lastVisitedId) : undefined;

  const toggleStatus = (status: WorkflowStatus) => {
    setStatuses((current) =>
      current.includes(status) ? current.filter((item) => item !== status) : [...current, status],
    );
  };
  const applyView = (viewId: string) => {
    queryClient.removeQueries({ queryKey: queryKeys.requirementLists() });
    setSelectedViewId(viewId);
    const view = savedViews.data?.find((item) => item.id === viewId);
    if (!view) { setViewName(""); return; }
    setViewName(view.name);
    setSearch(view.criteria.query ?? "");
    setStatuses(view.criteria.workflow_statuses ?? []);
    setSort(view.criteria.sort);
    setOwnerId(view.criteria.owner_id ?? "");
    setAssignedToMe(view.criteria.assigned_to_me);
  };

  const clearFilters = () => { setSearch(""); setStatuses([]); setOwnerId(""); setAssignedToMe(false); };

  return (
    <>
      <PageHeader
        title="Requirements"
        description="Move business needs from capture to a reviewed, traceable backlog."
      >
        {(lastVisited || latestDraft || firstLegacyDraft) && (
          /* "Where you left off", which the product was already collecting and
             never offering back (docs/ux-plan.md §3.12). */
          <p className="text-meta m-0 flex flex-wrap items-center gap-4">
            {lastVisited && (
              <Link className="text-accent inline-flex min-h-6 items-center gap-1.5 font-semibold underline underline-offset-2" to={stagePath(lastVisited)}>
                <span>Resume {lastVisited.title}</span>
                <span className="text-ink-muted font-normal">· {stageLabels[lastVisited.current_stage]}</span>
              </Link>
            )}
            {latestDraft && (
              <Link className="text-accent inline-flex min-h-6 items-center font-semibold underline underline-offset-2" to={`/requirements/new?draft=${latestDraft.id}`}>
                Resume {latestDraft.title || "untitled requirement"}
              </Link>
            )}
            {firstLegacyDraft && (
              <Button variant="text" disabled={claimDraft.isPending} onClick={() => claimDraft.mutate(firstLegacyDraft.id)}>
                Claim {firstLegacyDraft.title || "untitled draft"}
              </Button>
            )}
          </p>
        )}
      </PageHeader>

      {!requirements.isPending && !requirements.isError && attention.length > 0 && (
        <div className="mb-8">
          <AttentionStrip
            items={attention}
            open={attentionOpen}
            onToggle={() => setAttentionOpen((current) => !current)}
          />
        </div>
      )}

      <h2 className="text-headline m-0 mb-3" id="worklist-title">All requirements</h2>
      <section className="border-line bg-surface rounded-md border border-solid" aria-labelledby="worklist-title">
        <WorklistToolbar
          total={firstPage?.total}
          counts={counts}
          statuses={statuses}
          onToggleStatus={toggleStatus}
          search={search}
          onSearch={setSearch}
          ownerId={ownerId}
          onOwner={setOwnerId}
          ownerFacets={firstPage?.owner_facets ?? []}
          assignedToMe={assignedToMe}
          onAssigned={setAssignedToMe}
          sort={sort}
          onSort={setSort}
          hasFilters={hasFilters}
          onClearFilters={clearFilters}
          views={
            <SavedViewsMenu
              views={savedViews.data ?? []}
              selectedViewId={selectedViewId}
              onSelectView={applyView}
              viewName={viewName}
              onViewName={setViewName}
              onSave={() => createView.mutate()}
              onUpdate={() => updateView.mutate()}
              onDelete={() => deleteView.mutate()}
              saving={createView.isPending || updateView.isPending || deleteView.isPending}
              error={savedViews.error ?? createView.error ?? updateView.error ?? deleteView.error}
            />
          }
        />

        <AsyncState
          status={asyncStatus(requirements, list.length === 0)}
          loading={{ label: "Loading requirements", variant: "row", bars: 4 }}
          error={{ title: "We couldn’t load the worklist", message: errorMessage(requirements.error) }}
          onRetry={() => void requirements.refetch()}
          empty={{
            title: hasFilters ? "No matching requirements" : "No requirements yet",
            message: hasFilters
              ? "Try a different search or clear the filters."
              : "Capture the first business need to begin the review journey.",
            action: hasFilters
              ? <Button variant="secondary" onClick={clearFilters}>Clear filters</Button>
              : <ButtonLink variant="primary" to="/requirements/new">Create requirement</ButtonLink>,
          }}
        >
          <WorklistTable items={list} sort={sort} onSort={setSort} />
          {requirements.hasNextPage ? (
            <div className="border-line border-0 border-t border-solid p-3 text-center">
              <Button
                variant="secondary"
                loading={requirements.isFetchingNextPage}
                loadingLabel="Loading…"
                onClick={() => requirements.fetchNextPage()}
              >
                Load more
              </Button>
            </div>
          ) : null}
        </AsyncState>
      </section>
    </>
  );
}
