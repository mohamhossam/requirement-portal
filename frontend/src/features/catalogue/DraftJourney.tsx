import { useMutation, useQuery, useQueryClient, type UseMutationResult } from "@tanstack/react-query";
import { Check, Circle, CircleDot, FileSpreadsheet, PencilLine, Sparkles, Trash2, TriangleAlert } from "lucide-react";
import { useState, type ReactNode } from "react";

import { errorMessage } from "../../api/errors";
import { knowledgeApi, type ArchitectureJob, type KnowledgeRelease } from "../../api/knowledge";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { ErrorNotice } from "../../components/ErrorNotice";
import { AsyncState, asyncStatus } from "../../components/states";
import { Badge, Button, Tab, TabList, TabPanel, Tabs, Textarea, cx } from "../../components/ui";
import { FOCUS_RING, HOVER_GROUND, TRANSITION } from "../../components/ui/recipes";
import { CatalogueFileImport } from "./CatalogueFileImport";
import { DiffList } from "./DiffList";
import { DocumentSources } from "./DocumentSources";
import { ImpactComparison } from "./ImpactComparison";
import { JobStatus } from "./JobStatus";
import { catalogueKeys } from "./keys";
import { changeStory, versionName } from "./labels";
import { SuggestionList } from "./SuggestionList";
import { DomainsEditor } from "./DomainsEditor";
import { JourneysEditor } from "./JourneysEditor";
import { ProductsEditor } from "./ProductsEditor";
import { SystemsEditor } from "./SystemsEditor";
import { VersionNameDialog } from "./VersionNameDialog";

export type Step = "content" | "review" | "build" | "publish";
const REVIEWED_KEY = "catalogue:reviewed:";

/** The revision someone confirmed in Review changes, for this version, in this browser. */
function readReviewed(releaseId: string): number | null {
  try {
    const value = Number.parseInt(window.localStorage.getItem(`${REVIEWED_KEY}${releaseId}`) ?? "", 10);
    return Number.isFinite(value) ? value : null;
  } catch {
    return null;
  }
}

function writeReviewed(releaseId: string, revision: number) {
  try {
    window.localStorage.setItem(`${REVIEWED_KEY}${releaseId}`, String(revision));
  } catch {
    // Private windows and blocked storage: the review simply is not remembered.
  }
}

const STEPS: { key: Step; label: string }[] = [
  { key: "content", label: "Add content" },
  { key: "review", label: "Review changes" },
  { key: "build", label: "Build evidence index" },
  { key: "publish", label: "Publish" },
];

/**
 * The four steps as the stage rail draws a journey: a check once done, the
 * accent wash and edge on the step open in the workbench, a hollow ring
 * otherwise. Every step stays reachable; the rail only says which are done.
 */
function Stepper({ current, done, onSelect }: {
  current: Step | null;
  done: Record<Step, boolean>;
  onSelect: (step: Step) => void;
}) {
  return (
    <nav aria-label="Steps to publish this version">
      <ol className="m-0 grid list-none gap-1 p-0 sm:grid-cols-4 lg:grid-cols-1">
        {STEPS.map(({ key, label }, index) => {
          const active = key === current;
          const Icon = done[key] ? Check : active ? CircleDot : Circle;
          return (
            <li key={key}>
              <button
                type="button"
                aria-current={active ? "step" : undefined}
                aria-label={`Step ${index + 1}: ${label}${done[key] ? ", done" : ""}`}
                onClick={() => onSelect(key)}
                className={cx(
                  "text-body flex min-h-9 w-full cursor-pointer items-center gap-2 rounded-sm border-0 border-l-[3px] border-solid px-3 py-1 text-left",
                  active
                    ? "border-l-[var(--accent)] bg-accent-wash text-accent font-semibold"
                    : cx("border-l-transparent bg-transparent", done[key] ? "text-ink" : "text-ink-muted", HOVER_GROUND),
                  FOCUS_RING,
                  TRANSITION,
                )}
              >
                <Icon aria-hidden="true" size={16} className={cx("shrink-0", done[key] && "text-success")} />
                <span className="min-w-0">{label}</span>
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

function ChangesStep({ draft, onReviewed, onAddContent }: {
  draft: KnowledgeRelease;
  onReviewed: () => void;
  onAddContent: () => void;
}) {
  const changes = useQuery({
    queryKey: [...catalogueKeys.changes(draft.id), draft.revision],
    queryFn: () => knowledgeApi.changes(draft.id),
  });
  return (
    <section className="grid gap-4" aria-labelledby="review-title">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="grid gap-1">
          <h2 className="text-headline text-ink m-0" id="review-title" tabIndex={-1}>Review what this version changes</h2>
          <p className="text-meta text-ink-muted m-0">Compared with the version in use today.</p>
        </div>
        {/* The step's one way on sits beside its title, not after a list of any length. */}
        {(changes.data?.changes.length ?? 0) > 0 && (
          <Button variant="primary" onClick={onReviewed}>These changes are right — continue</Button>
        )}
      </div>
      <AsyncState
        status={asyncStatus(changes)}
        loading={{ label: "Comparing with the version in use", variant: "row", bars: 3 }}
        error={{ message: errorMessage(changes.error) }}
        onRetry={() => void changes.refetch()}
        headingLevel="h3"
      >
        {changes.data && (
          <DiffList diff={changes.data} empty="Nothing differs from the version in use yet. Add content first." />
        )}
        {changes.data?.changes.length === 0 && (
          <Button className="w-fit" onClick={onAddContent}>Add content</Button>
        )}
      </AsyncState>
    </section>
  );
}

const BUILD_HINTS = {
  queued: "Waiting for the background worker. Other reading or index jobs may be ahead of it.",
  running: "Building the index for your latest changes…",
};

/** The revision a build job was for; its fingerprint starts with it ("12|profile"). */
const buildRevision = (job: ArchitectureJob) => Number.parseInt(job.fingerprint, 10);

type IndexBuild = {
  loaded: boolean;
  /** The latest build for the draft's current revision, if there is one. */
  job: ArchitectureJob | null;
  start: UseMutationResult<ArchitectureJob, Error, KnowledgeRelease>;
  finished: () => void;
};

/** The build of record for a draft, read from the server so it survives a reload. */
function useIndexBuild(draft: KnowledgeRelease, onChanged: () => void): IndexBuild {
  const client = useQueryClient();
  const latest = useQuery({
    queryKey: catalogueKeys.build(draft.id),
    queryFn: () => knowledgeApi.buildStatus(draft.id),
  });
  const refresh = () => {
    void client.invalidateQueries({ queryKey: catalogueKeys.build(draft.id) });
    onChanged();
  };
  const start = useMutation({
    mutationFn: knowledgeApi.build,
    onSuccess: (job) => {
      // The started (or re-queued) job replaces a failed one at once, before the refetch.
      client.setQueryData(catalogueKeys.build(draft.id), job);
      refresh();
    },
  });
  const job = latest.data && buildRevision(latest.data) === draft.revision ? latest.data : null;
  return { loaded: latest.isSuccess, job, start, finished: refresh };
}

function BuildJob({ build, label, onFinished }: {
  build: IndexBuild;
  label: string;
  onFinished?: (job: ArchitectureJob) => void;
}) {
  if (!build.job) return null;
  return (
    <JobStatus key={`${build.job.id}-${build.job.attempts}`} job={build.job} label={label}
      hints={BUILD_HINTS} onFinished={(finished) => { build.finished(); onFinished?.(finished); }} />
  );
}

function BuildStep({ draft, built, build }: { draft: KnowledgeRelease; built: boolean; build: IndexBuild }) {
  // Opening this step only shows where the index stands; building is always the
  // person's act (the Build button here, or Build and publish on the last step).
  const { job, start } = build;

  return (
    <section className="grid gap-4" aria-labelledby="build-title">
      <div className="grid gap-1">
        <h2 className="text-headline text-ink m-0" id="build-title" tabIndex={-1}>Build the evidence index</h2>
        <p className="text-meta text-ink-muted m-0 max-w-[var(--measure-interface)]">
          The index is how requirement mapping finds these systems and quotes their source documents.
        </p>
      </div>
      {built ? (
        <p className="text-body text-ink-soft m-0 flex items-center gap-2" role="status">
          <Check className="text-success" size={16} aria-hidden="true" /> The index matches the latest changes.
        </p>
      ) : !job && (
        <>
          <p className="bg-warning-wash text-ink-soft text-meta m-0 flex w-fit gap-2 rounded-sm border-0 border-l-[3px] border-solid border-l-[var(--warning-edge)] px-3 py-2">
            <TriangleAlert className="text-warning mt-0.5 shrink-0" size={14} aria-hidden="true" />
            Not built for the latest changes. Requirement mapping cannot use this version until it is.
          </p>
          <Button variant="primary" className="w-fit" loading={start.isPending} loadingLabel="Starting…"
            onClick={() => start.mutate(draft)}>
            Build evidence index
          </Button>
        </>
      )}
      {start.error && <ErrorNotice message={errorMessage(start.error)} />}
      {!built && <BuildJob build={build} label="Evidence index" />}
      {built && <ImpactComparison draft={draft} />}
    </section>
  );
}

function PublishStep({ draft, built, build, onPublished }: {
  draft: KnowledgeRelease;
  built: boolean;
  build: IndexBuild;
  onPublished: () => void;
}) {
  const [rationale, setRationale] = useState("");
  const [confirming, setConfirming] = useState(false);
  // Set when someone chose "Build and publish": publishing follows a successful build.
  const [requested, setRequested] = useState(false);
  const changes = useQuery({
    queryKey: [...catalogueKeys.changes(draft.id), draft.revision],
    queryFn: () => knowledgeApi.changes(draft.id),
  });
  const publish = useMutation({ mutationFn: knowledgeApi.publish, onSuccess: () => { setConfirming(false); onPublished(); } });
  const { job, start } = build;
  const failed = job !== null && ["failed", "cancelled"].includes(job.status);
  const publishNow = () => {
    setRequested(false);
    publish.mutate({ release: draft, rationale });
  };
  const afterBuild = (finished: ArchitectureJob) => {
    if (!requested) return;
    if (finished.status === "succeeded") publishNow();
    else setRequested(false);
  };

  const confirm = () => {
    setConfirming(false);
    if (built) {
      publishNow();
      return;
    }
    setRequested(true);
    if (job && !failed) return; // Already building: its end decides.
    start.mutate(draft, {
      // Without a background worker the build has already finished here.
      onSuccess: (started) => afterBuildStart(started),
      onError: () => setRequested(false),
    });
  };
  const afterBuildStart = (started: ArchitectureJob) => {
    if (started.status === "succeeded") publishNow();
    else if (["failed", "cancelled"].includes(started.status)) setRequested(false);
  };
  const summary = changes.data ? changeStory(changes.data) : "";
  const impact = useQuery({ queryKey: catalogueKeys.mappingImpact, queryFn: knowledgeApi.mappingImpact });
  const mapped = impact.data;
  const affected = mapped && mapped.requirements > 0
    ? `${mapped.requirements} ${mapped.requirements === 1 ? "requirement" : "requirements"} (${mapped.features} features, ${mapped.stories} stories) will then show as mapped with an older version until their teams remap them; remapping resets their approvals.`
    : "Existing mappings are flagged as using an older catalogue until they are remapped.";
  const reason = !rationale.trim() ? "Say what you checked before publishing." : undefined;
  return (
    <section className="grid max-w-[var(--measure-interface)] gap-4" aria-labelledby="publish-title">
      <div className="grid gap-1">
        <h2 className="text-headline text-ink m-0" id="publish-title" tabIndex={-1}>Publish this version</h2>
        <p className="text-meta text-ink-muted m-0">
          Requirement mapping switches to it. The previous version stays in the history and can be made active again.
        </p>
      </div>
      <p className="text-body text-ink-soft m-0">
        {draft.systems.length} systems · {draft.relationships.length} dependencies · {draft.documents.length} source documents
      </p>
      {mapped && mapped.requirements > 0 && (
        <p className="bg-warning-wash text-ink-soft text-meta m-0 flex gap-2 rounded-sm border-0 border-l-[3px] border-solid border-l-[var(--warning-edge)] px-3 py-2">
          <TriangleAlert className="text-warning mt-0.5 shrink-0" size={14} aria-hidden="true" />
          <span>{affected}</span>
        </p>
      )}
      {!built && (
        <p className="text-meta text-ink-muted m-0">
          The evidence index is not built for the latest changes yet; it is built first, then this version is published.
        </p>
      )}
      <Textarea label="What did you check?" hint="Kept with the publication record." rows={3} required
        placeholder="Example: Compared with the March integration map; confirmed with the platform leads"
        value={rationale} onChange={(event) => setRationale(event.target.value)} />
      {publish.error && <ErrorNotice message={errorMessage(publish.error)} />}
      {start.error && <ErrorNotice message={errorMessage(start.error)} />}
      {requested && <BuildJob build={build} label="Building before publishing" onFinished={afterBuild} />}
      {!requested && failed && !built && (
        <p className="text-body text-ink-soft m-0" role="status">
          The last index build did not finish, so nothing is published. Build and publish tries it again.
        </p>
      )}
      <Button variant="primary" className="w-fit" blockedReason={reason} loading={requested || publish.isPending}
        loadingLabel={requested ? "Building the index…" : "Publishing…"} onClick={() => setConfirming(true)}>
        {built ? "Publish this version" : "Build and publish"}
      </Button>
      {confirming && (
        <ConfirmDialog
          title="Publish this version?"
          message={`${summary ? `${summary}. ` : ""}New requirement mappings use it straight away. ${affected}`}
          confirmLabel={built ? "Publish" : "Build and publish"}
          onCancel={() => setConfirming(false)}
          onConfirm={confirm}
        />
      )}
    </section>
  );
}

/** What the next step asks of a person, in their words. */
function nextAction(step: Step, pending: number) {
  switch (step) {
    case "content":
      return pending > 0
        ? `Review ${pending} AI ${pending === 1 ? "suggestion" : "suggestions"} waiting in Add content.`
        : "Add content from architecture documents, a catalogue file, or by hand.";
    case "review":
      return "Check what this version changes against the version in use.";
    case "build":
      return "Build the evidence index for the latest changes.";
    default:
      return "Publish this version, saying what you checked.";
  }
}

export type DraftParts = {
  /** The version in progress on the Change desk: its name, the steps, what is next. */
  desk: ReactNode;
  /** The open step's workspace, for the workbench; null when no step is open. */
  workspace: ReactNode;
  /** AI suggestions still waiting for a person. */
  pending: number;
  /** One line for the folded desk on narrow screens. */
  summary: ReactNode;
};

/**
 * A version in progress, as four steps: add content (three ways), review the
 * changes, build the index, publish. It owns the workflow and hands its two
 * faces to the page: the desk that says where the version stands and what is
 * next, and the open step's workspace. `step` is which step the workbench
 * shows: "auto" follows the first step not yet done, null shows none.
 */
export function DraftJourney({
  draft,
  step: requested,
  onStep,
  onChanged,
  onPublished,
  onDiscarded,
  children,
}: {
  draft: KnowledgeRelease;
  step: Step | "auto" | null;
  onStep: (step: Step | null) => void;
  onChanged: () => void;
  onPublished: () => void;
  onDiscarded: () => void;
  children: (parts: DraftParts) => ReactNode;
}) {
  const [renaming, setRenaming] = useState(false);
  const [discarding, setDiscarding] = useState(false);
  const rename = useMutation({
    mutationFn: (name: string) => knowledgeApi.rename(draft, name),
    onSuccess: () => { setRenaming(false); onChanged(); },
  });
  const discard = useMutation({ mutationFn: () => knowledgeApi.discard(draft), onSuccess: onDiscarded });
  const suggestions = useQuery({
    queryKey: catalogueKeys.suggestions(draft.id),
    queryFn: () => knowledgeApi.suggestions(draft.id),
  });
  // Kept per version in this browser, so a reload does not send the person back to a review they finished.
  const [reviewedRevision, setReviewed] = useState<number | null>(() => readReviewed(draft.id));
  const setReviewedRevision = (revision: number) => {
    setReviewed(revision);
    writeReviewed(draft.id, revision);
  };
  const built = draft.built_revision === draft.revision;
  const build = useIndexBuild(draft, onChanged);
  const pending = suggestions.data?.suggestions.filter((item) => item.status === "proposed").length ?? 0;
  const done: Record<Step, boolean> = {
    content: draft.systems.length > 0 && pending === 0,
    review: reviewedRevision === draft.revision || built,
    build: built,
    publish: false,
  };
  const firstOpen = STEPS.find(({ key }) => !done[key])?.key ?? "publish";
  const step = requested === "auto" ? firstOpen : requested;
  const firstOpenLabel = STEPS.find(({ key }) => key === firstOpen)?.label;

  const desk = (
    <section aria-labelledby="draft-title" className="grid gap-4">
      <div className="grid min-w-0 gap-1.5">
        <h2 className="text-headline text-ink m-0 break-words" id="draft-title">{versionName(draft)}</h2>
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <Badge tone="warning">In progress</Badge>
          {draft.created_by && <span className="text-meta text-ink-muted">started by {draft.created_by}</span>}
        </div>
      </div>
      {/* The one instruction on the page, first on the desk. It is the filled
          action only while no step holds the workbench; inside a step, that
          step's own action is the filled one. The edge and the white sheet mark
          it; a full frame inside the desk would be a card in a card. */}
      <div className="bg-surface grid gap-2 rounded-sm border-0 border-l-[3px] border-solid border-l-[var(--accent)] p-3">
        <p className="text-label text-accent m-0">NEXT</p>
        <p className="text-body text-ink m-0">{nextAction(firstOpen, pending)}</p>
        {step !== firstOpen ? (
          <Button size="sm" variant={step ? "secondary" : "primary"} className="w-fit" onClick={() => onStep(firstOpen)}>
            Open {firstOpenLabel}
          </Button>
        ) : (
          <p className="text-meta text-ink-muted m-0">This step is open in the workbench.</p>
        )}
      </div>
      <Stepper current={step} done={done} onSelect={onStep} />
      <div className="flex flex-wrap gap-1">
        <Button size="sm" variant="ghost" icon={<PencilLine size={14} aria-hidden="true" />}
          onClick={() => { rename.reset(); setRenaming(true); }}>
          Rename
        </Button>
        <Button size="sm" variant="ghost" icon={<Trash2 size={14} aria-hidden="true" />}
          onClick={() => { discard.reset(); setDiscarding(true); }}>
          Remove this version
        </Button>
      </div>
      {discard.error && <ErrorNotice message={errorMessage(discard.error)} />}
      {renaming && (
        <VersionNameDialog
          title="Rename this version"
          description="The name is how the team finds this version in the history."
          initial={draft.name ?? ""}
          confirmLabel="Rename"
          saving={rename.isPending}
          error={rename.error ? errorMessage(rename.error) : null}
          onSubmit={(name) => rename.mutate(name)}
          onCancel={() => setRenaming(false)}
        />
      )}
      {discarding && (
        <ConfirmDialog
          title={`Remove “${versionName(draft)}”?`}
          message="Its changes, source-document list, AI suggestions and evidence index are deleted. Published versions and the version in use are not affected. This cannot be undone."
          confirmLabel="Remove version"
          onCancel={() => setDiscarding(false)}
          onConfirm={() => { setDiscarding(false); discard.mutate(); }}
        />
      )}
    </section>
  );

  const ahead = step !== null && STEPS.findIndex(({ key }) => key === step) > STEPS.findIndex(({ key }) => key === firstOpen);
  const workspace = step ? (
    <div className="grid min-w-0 gap-6">
      {/* Every step stays reachable, but working ahead of an unfinished one is said out loud, never blocked. */}
      {ahead && (
        <div className="bg-warning-wash flex flex-wrap items-center justify-between gap-x-4 gap-y-2 rounded-sm border-0 border-l-[3px] border-solid border-l-[var(--warning-edge)] px-3 py-2">
          <p className="text-meta text-ink-soft m-0 flex items-center gap-2">
            <TriangleAlert className="text-warning shrink-0" size={14} aria-hidden="true" />
            {firstOpenLabel} isn’t done yet. You can carry on here, or finish it first.
          </p>
          <Button size="sm" onClick={() => onStep(firstOpen)}>Open {firstOpenLabel}</Button>
        </div>
      )}
      {step === "content" && (
        <section aria-labelledby="content-title" className="grid gap-4">
          <h2 className="text-headline text-ink m-0" id="content-title" tabIndex={-1}>Add content</h2>
          <Tabs defaultValue="documents">
            <TabList label="Ways to add content">
              <Tab value="documents" icon={<Sparkles size={16} aria-hidden="true" />} count={pending || undefined}>
                From documents
              </Tab>
              <Tab value="file" icon={<FileSpreadsheet size={16} aria-hidden="true" />}>Upload catalogue file</Tab>
              <Tab value="manual" icon={<PencilLine size={16} aria-hidden="true" />}>Edit manually</Tab>
            </TabList>
            <TabPanel value="documents" className="grid gap-8 pt-4">
              <DocumentSources draft={draft} onChanged={onChanged} />
              <SuggestionList draft={draft} onChanged={onChanged} />
            </TabPanel>
            <TabPanel value="file" className="pt-4">
              <CatalogueFileImport draft={draft} onChanged={onChanged} />
            </TabPanel>
            <TabPanel value="manual" className="grid gap-8 pt-4">
              <SystemsEditor draft={draft} onChanged={onChanged} />
              <ProductsEditor draft={draft} onChanged={onChanged} />
              <JourneysEditor draft={draft} onChanged={onChanged} />
              <DomainsEditor draft={draft} onChanged={onChanged} kind="landscape" />
              <DomainsEditor draft={draft} onChanged={onChanged} />
            </TabPanel>
          </Tabs>
        </section>
      )}
      {step === "review" && (
        <ChangesStep draft={draft} onAddContent={() => onStep("content")}
          onReviewed={() => { setReviewedRevision(draft.revision); onStep("build"); }} />
      )}
      {step === "build" && <BuildStep draft={draft} built={built} build={build} />}
      {step === "publish" && <PublishStep draft={draft} built={built} build={build} onPublished={onPublished} />}
    </div>
  ) : null;

  const summary = (
    <span className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
      <Badge tone="warning">In progress</Badge>
      <span className="font-semibold break-words">{versionName(draft)}</span>
      <span className="text-meta text-ink-muted">Next: {firstOpenLabel}</span>
    </span>
  );

  return <>{children({ desk, workspace, pending, summary })}</>;
}
