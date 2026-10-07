import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, History, PanelRight, Users } from "lucide-react";
import { lazy, Suspense, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "../api/client";
import { errorMessage } from "../api/errors";
import { useAuth } from "../auth/authContext";
import { PageHeader } from "../components/shell";
import { Skeleton } from "../components/Skeleton";
import { ErrorState, LoadingState } from "../components/states";
import { Button, ButtonLink } from "../components/ui/Button";
import { WorkspaceDrawer } from "../components/WorkspaceDrawer";
import { AiJobStatusPanel } from "../features/jobs/AiJobStatusPanel";
import { RequirementJobsProvider } from "../features/jobs/RequirementJobsProvider";
import { useRequirementJobs } from "../features/jobs/useRequirementJobs";
import { useLazyKnowledgeScreening } from "../features/knowledge/useLazyKnowledgeScreening";
import { queryKeys } from "./queryKeys";
import { journey, nextAction } from "./requirement/journey";
import { NextAction } from "./requirement/NextAction";
import { RailSlotOutlet, RailSlotProvider } from "./requirement/RailSlot";
import { StageRail } from "./requirement/StageRail";
import { useRequirementWorkspace } from "./requirement/useRequirementWorkspace";

/**
 * One chunk per stage, not one chunk per workspace.
 *
 * `RequirementPage` is already behind a route-level `lazy()`, but it pulled all
 * seven stage surfaces in statically, so opening the Backlog downloaded Clarify,
 * Knowledge, Review, Revisions and the Source panel with it. Measured: the
 * non-Backlog stage sources total 97.8 kB against 86.9 kB for the Backlog, so
 * roughly half that chunk was code for a stage nobody was looking at.
 *
 * Each stage renders inside a local `Suspense` below, never the route-level one
 * — bubbling to that would unmount the whole workspace, header and rail
 * included, every time somebody moved between steps.
 */
const loadCapture = () => import("./requirement/CaptureView");
const loadAnalysis = () => import("./requirement/AnalysisView");
const loadKnowledge = () => import("./requirement/KnowledgeView");
const loadBreakdown = () => import("./requirement/BreakdownView");
const loadReview = () => import("../features/review/BreakdownReviewPanel");
const loadRevisions = () => import("./requirement/RevisionsView");

const CaptureView = lazy(() => loadCapture().then((m) => ({ default: m.CaptureView })));
const AnalysisView = lazy(() => loadAnalysis().then((m) => ({ default: m.AnalysisView })));
const KnowledgeView = lazy(() => loadKnowledge().then((m) => ({ default: m.KnowledgeView })));
const BreakdownView = lazy(() => loadBreakdown().then((m) => ({ default: m.BreakdownView })));
const BreakdownReviewPanel = lazy(() => loadReview().then((m) => ({ default: m.BreakdownReviewPanel })));
const RevisionsView = lazy(() => loadRevisions().then((m) => ({ default: m.RevisionsView })));

/**
 * Which chunk this route is going to need, so it can be fetched alongside the
 * requirement instead of after it.
 *
 * Splitting the stages cost a round trip that splitting was supposed to save:
 * a stage only starts loading when it first renders, and it first renders once
 * the requirement resolves, so the chunk fetch landed between the requirement
 * and the stage's own queries. Warming it on mount puts that fetch in the same
 * wave as the requirement. React.lazy caches the module promise, so the render
 * below reuses this fetch rather than starting a second one.
 */
const STAGE_LOADER: Record<string, () => Promise<unknown>> = {
  capture: loadCapture,
  clarify: loadAnalysis,
  confirm: loadAnalysis,
  knowledge: loadKnowledge,
  breakdown: loadBreakdown,
  review: loadReview,
  revisions: loadRevisions,
};

/* The two drawers, which only load once somebody opens them. */
const SourcePanel = lazy(() => import("./requirement/SourcePanel").then((m) => ({ default: m.SourcePanel })));
const SourceConfirmation = lazy(() => import("./requirement/SourcePanel").then((m) => ({ default: m.SourceConfirmation })));
const RequirementAccessPanel = lazy(() => import("../features/identity/RequirementAccessPanel").then((m) => ({ default: m.RequirementAccessPanel })));
import { useSourceEditing } from "./requirement/useSourceEditing";
import { useDocumentTitle } from "./useDocumentTitle";

type RequirementView = "capture" | "clarify" | "knowledge" | "confirm" | "breakdown" | "review" | "revisions";

/**
 * The stage, for the document title and for the line under the requirement's
 * name. It is no longer the `h1`: docs/ux-plan.md §3.4 counted five labels above
 * the first question on `/clarify`, with the requirement's own title demoted into
 * an eyebrow. The rail says which stage you are on; the heading says which
 * requirement you are in.
 */
const STAGES: Record<RequirementView, string> = {
  capture: "Source",
  clarify: "Clarify",
  knowledge: "Knowledge",
  confirm: "Confirm",
  breakdown: "Backlog",
  review: "Review & approve",
  revisions: "History",
};

const DESCRIPTIONS: Record<RequirementView, string> = {
  capture: "Check the business need and its files are ready to analyse.",
  clarify: "Answer the gaps and ambiguities identified by the analysis before proceeding.",
  knowledge: "Check whether this requirement repeats or conflicts with another, and decide each overlap.",
  confirm: "Review the extracted facts, rules, constraints, and resolved answers before confirmation.",
  breakdown: "Review the Epic, Features, and Stories generated from the confirmed source.",
  review: "Settle what the review found, read the evidence, then sign off the backlog.",
  revisions: "Download the approved backlog, and see what changed between versions.",
};

export function RequirementPage({ view }: { view: RequirementView }) {
  const { id = "" } = useParams();
  const auth = useAuth();
  // Warm this stage's chunk on mount, so it downloads beside the requirement
  // rather than in the gap between the requirement resolving and the stage
  // first rendering. See STAGE_LOADER.
  useEffect(() => { void STAGE_LOADER[view]?.(); }, [view]);
  return (
    <RequirementJobsProvider key={JSON.stringify([queryKeys.aiJobs(id), auth?.actor?.id])} requirementId={id}>
      <RequirementWorkspaceShell view={view} />
    </RequirementJobsProvider>
  );
}

/**
 * One frame for all seven stages, Backlog included.
 *
 * docs/ux-plan.md §3.3: "Backlog is a different application" — a different shell
 * class, a different header variant, no sidebar, no full stepper, and Source and
 * People demoted to drawers on that one route. §4 answers it: same shell, same
 * stage rail, same Source and People affordances, everywhere.
 * `adr-0045-focused-breakdown-workspace` is superseded. What survives is the
 * Backlog's own Epic to Feature to Story tree, which is legitimate depth *within*
 * a step rather than a second navigation system.
 *
 * Source and People are drawers on **every** stage, at every width. §4 asks for
 * "panels, not stage-dependent shapeshifting", and each of them previously had two
 * implementations — a sticky rail or a `<details>` on six routes, a drawer on the
 * seventh. One implementation, one affordance, the same three buttons in the same
 * place on all seven routes.
 *
 * Each stage still owns the reads and writes only it uses, so mounting is what
 * gates them.
 */
function RequirementWorkspaceShell({ view }: { view: RequirementView }) {
  const { id = "" } = useParams();
  const auth = useAuth();
  const jobs = useRequirementJobs(id);
  const workspace = useRequirementWorkspace(id);
  const { requirement, assignments, analysis, knowledgeReview, priorArt } = workspace;
  const [drawer, setDrawer] = useState<"source" | "people" | null>(null);
  const source = useSourceEditing({ id, requirement: requirement.data, refresh: workspace.refresh });

  useEffect(() => {
    if (requirement.data) localStorage.setItem("lastRequirementId", requirement.data.id);
  }, [requirement.data]);

  // Started here rather than inside the knowledge stage, because arriving at
  // confirmation has to ensure a screen exists too.
  const isKnowledgeTeamMember = Boolean(
    assignments.data &&
      [assignments.data.owner?.actor, ...assignments.data.reviewers.map((item) => item.actor)]
        .some((actor) => actor?.id === auth?.actor?.id),
  );
  const screeningActive = jobs.active.some((job) => job.operation === "screen_requirement_knowledge");
  // The same ensure also asks for a similar-past-requirements check (Knowledge Center E2):
  // when the screen is current but the historic corpus has moved on, it still fires.
  const priorArtActive = jobs.active.some((job) => job.operation === "screen_prior_art");
  const needsScreen =
    (knowledgeReview.data?.status === "required" || knowledgeReview.data?.status === "stale") && !screeningActive;
  const needsPriorArt =
    (priorArt.data?.status === "not_checked" || priorArt.data?.status === "out_of_date") && !priorArtActive;
  const ensureScreen = useLazyKnowledgeScreening({
    requirementId: id,
    fingerprint: knowledgeReview.data
      ? `${knowledgeReview.data.input_fingerprint}:${priorArt.data?.input_key ?? ""}`
      : undefined,
    enabled:
      (view === "knowledge" || view === "confirm") &&
      isKnowledgeTeamMember &&
      requirement.data?.status !== "duplicate" &&
      (needsScreen || needsPriorArt),
  });
  const screening = {
    ...ensureScreen,
    running: screeningActive || ensureScreen.isPending ||
      ensureScreen.data?.outcome === "scheduled" || ensureScreen.data?.outcome === "already_scheduled",
  };

  // Read-only views of what the Backlog stage fetches, for the job panel's
  // Feature names and the stale flag. Disabled, so they never issue a request.
  const cachedEpic = useQuery({ queryKey: queryKeys.epic(id), queryFn: () => api.getEpic(id), enabled: false });
  const cachedFeatures = useQuery({ queryKey: queryKeys.features(id), queryFn: () => api.getFeatures(id), enabled: false });

  // Above the early returns, because a hook cannot be called after one. The
  // Requirement comes first: a reviewer with four of these open is looking for
  // which Requirement, not which stage.
  useDocumentTitle(requirement.data ? `${requirement.data.title} · ${STAGES[view]}` : null);

  if (requirement.isPending) {
    return (
      <LoadingState
        label="Opening the requirement workspace"
        variant="page"
        caption="Opening review workspace…"
      />
    );
  }
  if (requirement.isError || !requirement.data) {
    return (
      <ErrorState
        headingLevel="h2"
        title="We couldn’t open this requirement"
        message={errorMessage(requirement.error)}
        onRetry={() => void requirement.refetch()}
        action={<ButtonLink variant="primary" to="/">Return to requirements</ButtonLink>}
      />
    );
  }

  const data = requirement.data;
  const analysisData = analysis.data ?? null;
  const unresolvedCount = analysisData
    ? analysisData.questions.length || analysisData.assumptions.length + analysisData.open_questions.length +
      analysisData.ambiguities.length + analysisData.potential_dependencies.length
    : 0;
  const blockingCount = analysisData?.questions.length
    ? analysisData.questions.filter((question) => question.is_blocker).length
    : unresolvedCount;

  const journeyState = {
    eligible: data.analysis_eligibility.eligible,
    hasAnalysis: Boolean(analysisData),
    blockingCount,
    knowledgeReady: Boolean(knowledgeReview.data?.ready),
    humanConfirmed: Boolean(analysisData?.human_confirmed),
    isDuplicate: Boolean(data.duplicate_of_requirement_id),
  };
  const steps = journey(id, journeyState);
  const whatNext = nextAction(journeyState, steps);
  const viewingPath = `/requirements/${id}/${view}`;
  const breakdown = view === "breakdown";
  /**
   * The source drawer is open when somebody asked for it — or when something else
   * put the source into edit mode.
   *
   * The Capture stage has its own "Edit source" button that flips
   * `source.editing`, and the form it opens lives in this panel. While the panel
   * was a rail on that route the form simply appeared; now that it is a drawer
   * everywhere, the drawer has to follow the state rather than the click, or the
   * button would look broken. The same holds for a save waiting on its impact
   * acknowledgement: the confirmation is raised from inside the drawer, so the
   * drawer stays until it is answered.
   */
  const sourceOpen = drawer === "source" || source.editing || Boolean(source.pending);
  const stale = cachedEpic.data?.stale || cachedFeatures.data?.features.some((item) => item.stale);

  return (
    <div className="requirement-workspace">
      {/* First, not fourth. §3.12: on a Requirement closed as a duplicate this
          banner used to render below the AI job panel and the page heading —
          under two things that stop mattering the moment this turns out to be
          the wrong requirement. */}
      {data.duplicate_of_requirement_id && (
        <section
          className="border-line bg-warning-wash mb-4 rounded-md border border-solid border-l-[3px] border-l-[var(--warning-edge)] p-4"
          role="status"
        >
          <strong className="text-warning text-body">This requirement is closed as a duplicate.</strong>{" "}
          <span className="text-ink-soft text-body">
            Its history remains available, but analysis and backlog generation are disabled. The
            canonical requirement is{" "}
            <Link
              className="text-accent underline underline-offset-2"
              to={`/requirements/${data.duplicate_of_requirement_id}/knowledge`}
            >
              {data.duplicate_of_requirement_id.slice(0, 8)}
            </Link>
            .
          </span>
        </section>
      )}

      <PageHeader
        title={data.title}
        description={DESCRIPTIONS[view]}
        actions={
          <>
            {/* The same three, in the same order, on every stage. */}
            {/* "Source document", not "Source": step 1 of the rail is already
                called Source, and two controls of that name on one screen is one
                too many. docs/ux-plan.md §4 names the panel this way. */}
            <Button
              variant="secondary"
              icon={<PanelRight size={16} aria-hidden="true" />}
              onClick={() => setDrawer("source")}
            >
              Source document
            </Button>
            <Button
              variant="secondary"
              icon={<Users size={16} aria-hidden="true" />}
              onClick={() => setDrawer("people")}
            >
              People
            </Button>
            <ButtonLink
              aria-current={view === "revisions" ? "page" : undefined}
              variant="secondary"
              to={`/requirements/${id}/revisions`}
              icon={<History size={16} aria-hidden="true" />}
            >
              History
            </ButtonLink>
          </>
        }
      >
        <p className="text-ink-muted text-meta m-0">
          <span className="font-mono">{data.id.slice(0, 8)}</span> · {STAGES[view]}
        </p>
      </PageHeader>

      {/* The rail is a column once there is room for one beside the workspace, and
          a scrolling row of the same six links before that. Both are the same
          markup and the same model: the rail never stops being present, which is
          the whole of §4's "persistent stage rail". */}
      <RailSlotProvider>
      <div className="grid items-start gap-6 lg:grid-cols-[var(--stage-rail-width)_minmax(0,1fr)] lg:gap-8">
        {/* The spine. `overflow-y` arrives with the Backlog tree, which is the
            one thing in this column long enough to need it; `px-1` gives the
            2px focus offset room, because a scroll container clips a ring that
            sits on its own edge. */}
        <div className="grid min-w-0 gap-4 lg:sticky lg:top-[calc(var(--header-height)+var(--space-6))] lg:max-h-[calc(100dvh-var(--header-height)-var(--space-12))] lg:overflow-y-auto lg:-mx-2 lg:px-2">
          <StageRail steps={steps} viewingPath={viewingPath} />
          {/* Directly under the steps, and indented by the tree itself: it is
              depth inside step 5, so anything between the two reads as a
              seventh step rather than as the fifth one opening. */}
          <RailSlotOutlet />
          {whatNext && <NextAction action={whatNext} here={viewingPath} />}
        </div>

        <div className="workspace-body grid min-w-0 gap-4">
          {stale && (
            <p
              className="border-line bg-warning-wash text-body m-0 flex items-center gap-2 rounded-md border border-solid border-l-[3px] border-l-[var(--warning-edge)] px-3 py-2"
              role="status"
            >
              <AlertTriangle className="text-warning" size={17} aria-hidden="true" />
              <span className="text-ink-soft">Part of this backlog is out of date.</span>
            </p>
          )}

          <AiJobStatusPanel
            requirementId={id}
            focused={breakdown}
            featureNames={breakdown
              ? Object.fromEntries((cachedFeatures.data?.features ?? []).map((feature) => [feature.id, feature.name]))
              : undefined}
          />

          {assignments.isError && (
            <ErrorState
              title="We couldn’t load the people on this requirement"
              message={errorMessage(assignments.error)}
              onRetry={() => void assignments.refetch()}
            />
          )}

          <Suspense fallback={<Skeleton label="Loading this step" variant="page" />}>
            {view === "capture" && (
              <CaptureView id={id} requirement={data} canManageContent={workspace.canManageContent}
                canGovern={workspace.canGovern} source={source} refresh={workspace.refresh} />
            )}
            {(view === "clarify" || view === "confirm") && (
              <AnalysisView id={id} view={view} workspace={workspace} />
            )}
            {view === "knowledge" && <KnowledgeView id={id} workspace={workspace} screening={screening} />}
            {breakdown && <BreakdownView id={id} workspace={workspace} />}
            {view === "review" && (
              <BreakdownReviewPanel requirementId={id}
                canGenerate={workspace.canManageContent && Boolean(analysisData)}
                canManage={workspace.canManageContent} />
            )}
            {view === "revisions" && <RevisionsView id={id} workspace={workspace} />}
          </Suspense>
        </div>
      </div>
      </RailSlotProvider>

      {sourceOpen && (
        <WorkspaceDrawer
          title="Source document"
          onClose={() => { setDrawer(null); source.setEditing(false); }}
        >
          <Suspense fallback={<Skeleton label="Loading the source document" />}>
            <SourcePanel id={id} requirement={data} analysis={analysisData}
              canGovern={workspace.canGovern} source={source} refresh={workspace.refresh} />
            {/* Nested inside, not beside: the confirmation belongs to the save the
                person just made in this panel, and `Modal` stacks in the top layer
                so it traps its own Tab and Escape dismisses only the topmost. */}
            <SourceConfirmation source={source} />
          </Suspense>
        </WorkspaceDrawer>
      )}
      {drawer === "people" && assignments.data && (
        <WorkspaceDrawer title="People" onClose={() => setDrawer(null)}>
          <Suspense fallback={<Skeleton label="Loading the people on this requirement" />}>
            <RequirementAccessPanel requirementId={id} access={assignments.data} />
          </Suspense>
        </WorkspaceDrawer>
      )}
    </div>
  );
}
