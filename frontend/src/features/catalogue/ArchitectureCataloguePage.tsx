import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, CircleCheck, GitCompareArrows, Grid3x3, History, Layers, List, Package, Plus, Route } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";

import { errorMessage } from "../../api/errors";
import { knowledgeApi, type KnowledgeRelease } from "../../api/knowledge";
import { organisationApi, type Organisation } from "../../api/organisation";
import { useDocumentTitle } from "../../app/useDocumentTitle";
import { PageHeader } from "../../components/shell";
import { AsyncState, LoadingState, asyncStatus } from "../../components/states";
import { Button, Select, cx } from "../../components/ui";
import { CatalogueBrowser } from "./CatalogueBrowser";
import { CatalogueNav } from "./CatalogueNav";
import { ChangeDesk, LiveVersion } from "./ChangeDesk";
import { DependencyMatrix } from "./DependencyMatrix";
import { DomainTree } from "./DomainTree";
import { JourneysView } from "./JourneysView";
import { ProductsView } from "./ProductsView";
import { DraftJourney, type Step } from "./DraftJourney";
import { catalogueKeys } from "./keys";
import { changeStory, versionName } from "./labels";
import { ReleaseHistory } from "./ReleaseHistory";
import { VersionNameDialog } from "./VersionNameDialog";
import { Segmented } from "./WorkbenchControls";

const DESCRIPTION = "What each system does and depends on. Changes reach requirement mapping only when a new version is published.";

type View = "systems" | "matrix" | "domains" | "products" | "journeys" | "history";
type Showing = "active" | "draft";
type Notice = { text: string; tone: "success" | "neutral" } | null;

const VIEW_ICON = { size: 15, "aria-hidden": true } as const;
const STEP_KEYS: Step[] = ["content", "review", "build", "publish"];
/** The workbench's view as the URL spells it, so a view, a step and a system can be linked to and Back works. */
const VIEW_PARAM: Record<View, string> = {
  systems: "systems", matrix: "dependencies", domains: "domains", products: "products", journeys: "journeys", history: "history",
};

/**
 * One version of the landscape, as a list with a dossier or as the dependency
 * matrix. The diff of a version in progress is read here, not upstream, so the
 * version in use never waits on it; when there is one, a single line says what
 * the version does before anything else.
 */
function Landscape({ release, baseline, draft, organisation, view, heading, selected, onSelect, onOpenSystem }: {
  release: KnowledgeRelease;
  baseline: KnowledgeRelease | undefined;
  draft: KnowledgeRelease | undefined;
  organisation: Organisation | undefined;
  view: "systems" | "matrix" | "domains" | "products" | "journeys";
  heading: string;
  selected: string | null;
  onSelect: (id: string) => void;
  onOpenSystem: (id: string) => void;
}) {
  const changes = useQuery({
    queryKey: [...catalogueKeys.changes(draft?.id ?? ""), draft?.revision],
    queryFn: () => knowledgeApi.changes(draft!.id),
    enabled: Boolean(draft),
  });
  const diff = draft ? changes.data : undefined;
  const story = changeStory(diff);
  return (
    <div className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-5">
      {draft && (
        <p className="bg-surface-sunken border-line m-0 flex min-h-11 flex-wrap items-center gap-x-3 gap-y-1 rounded-md border border-solid px-4 py-1.5">
          <GitCompareArrows className="text-ink-muted shrink-0" size={16} aria-hidden="true" />
          <span className="text-body text-ink min-w-0 flex-1">
            {story || "Nothing differs from the version in use yet."}
          </span>
        </p>
      )}
      {view === "matrix"
        ? <DependencyMatrix release={release} baseline={baseline} diff={diff} onOpenSystem={onOpenSystem} />
        : view === "domains"
        ? <DomainTree release={release} diff={diff} onOpenSystem={onOpenSystem} />
        : view === "products"
        ? <ProductsView release={release} diff={diff} onOpenSystem={onOpenSystem} />
        : view === "journeys"
        ? <JourneysView release={release} diff={diff} onOpenSystem={onOpenSystem} />
        : <CatalogueBrowser release={release} baseline={baseline} organisation={organisation} heading={heading}
            diff={diff} selected={selected} onSelect={onSelect} />}
    </div>
  );
}

export function ArchitectureCataloguePage() {
  useDocumentTitle("Architecture catalogue");
  const client = useQueryClient();
  const me = useQuery({ queryKey: catalogueKeys.me, queryFn: knowledgeApi.me });
  const maintainer = Boolean(me.data?.roles?.includes("knowledge_maintainer"));
  const reader = maintainer || Boolean(me.data?.roles?.includes("knowledge_reader"));
  const releases = useQuery({ queryKey: catalogueKeys.releases, queryFn: knowledgeApi.releases, enabled: maintainer });
  const active = useQuery({ queryKey: catalogueKeys.active, queryFn: knowledgeApi.active, enabled: reader });
  const organisation = useQuery({ queryKey: catalogueKeys.organisation, queryFn: organisationApi.get, enabled: reader });
  const [selected, setSelected] = useState<string | null>(null);
  const [notice, setNotice] = useState<Notice>(null);
  const refresh = () => {
    void client.invalidateQueries({ queryKey: ["knowledge"] });
  };
  const impact = useQuery({ queryKey: catalogueKeys.mappingImpact, queryFn: knowledgeApi.mappingImpact,
    enabled: maintainer });
  const [naming, setNaming] = useState(false);

  // What the workbench shows lives in the URL: which version, which view of it,
  // which step of the change workflow (which wins over the view while one is
  // open), and which system's dossier is open. Defaults stay out of the URL.
  const [params, setParams] = useSearchParams();
  const showing: Showing = params.get("version") === "in-use" ? "active" : "draft";
  const view: View = (Object.keys(VIEW_PARAM) as View[])
    .find((key) => VIEW_PARAM[key] === params.get("view")) ?? "systems";
  const step = STEP_KEYS.find((key) => key === params.get("step")) ?? null;
  const system = params.get("system");
  // Views, versions and steps are places Back returns to; moving through the
  // systems (arrow keys included) replaces the entry rather than piling them up.
  const update = (changes: { version?: Showing; view?: View; step?: Step | null; system?: string | null }) => {
    const onlySystem = Object.keys(changes).every((key) => key === "system");
    setParams((currentParams) => {
      const next = new URLSearchParams(currentParams);
      const put = (key: string, value: string | null | undefined, fallback: string) => {
        if (value === undefined) return;
        if (value === null || value === fallback) next.delete(key);
        else next.set(key, value);
      };
      put("version", changes.version === undefined ? undefined : changes.version === "active" ? "in-use" : "in-progress", "in-progress");
      put("view", changes.view === undefined ? undefined : VIEW_PARAM[changes.view], "systems");
      put("step", changes.step, "");
      put("system", changes.system, "");
      return next;
    }, { replace: onlySystem });
  };
  // Opening a step moves focus to its heading, and closing one to the view it
  // returns to, so keyboard and screen-reader users land where the work now is.
  // The move waits for the render that shows the target: the button that asked
  // is usually gone by then, and a focus call made before it lands on nothing.
  const pendingFocus = useRef<"step" | "view" | null>(null);
  useEffect(() => {
    const want = pendingFocus.current;
    if (!want) return;
    const target = want === "step" && step
      ? document.getElementById(`${step}-title`)
      : document.querySelector<HTMLElement>('[role="group"][aria-label="View"] [aria-pressed="true"]');
    if (!target) return;
    pendingFocus.current = null;
    target.focus({ preventScroll: true });
    target.scrollIntoView?.({ block: "nearest" });
  });
  const openStep = (next: Step | null) => {
    pendingFocus.current = next ? "step" : "view";
    update(next ? { step: next, version: "draft" } : { step: null });
  };
  const create = useMutation({
    mutationFn: (name: string) => knowledgeApi.createDraft(name),
    onSuccess: (draft) => {
      setSelected(draft.id); setNotice(null); setNaming(false);
      update({ version: "draft", step: null });
      refresh();
    },
  });

  if (me.isPending) return <LoadingState label="Checking your access" variant="page" />;
  const header = <PageHeader title="Architecture catalogue" description={DESCRIPTION} />;
  if (!reader) {
    return <>{header}<CatalogueNav />
      <p className="text-body text-ink-soft m-0">Maintaining the catalogue needs the knowledge maintainer role. Ask an administrator for access.</p>
    </>;
  }

  const openSystem = (id: string) => update({ system: id, view: "systems", step: null });
  const viewSwitch = (views: View[], pressed: View | null, onChange: (value: View) => void) => (
    <Segmented<View> label="View" value={pressed} onChange={onChange} options={[
      { value: "systems" as const, label: "Systems", icon: <List {...VIEW_ICON} /> },
      { value: "matrix" as const, label: "Dependencies", icon: <Grid3x3 {...VIEW_ICON} /> },
      { value: "domains" as const, label: "Domains", icon: <Layers {...VIEW_ICON} /> },
      { value: "products" as const, label: "Product offerings", icon: <Package {...VIEW_ICON} /> },
      { value: "journeys" as const, label: "Journeys", icon: <Route {...VIEW_ICON} /> },
      { value: "history" as const, label: "History", icon: <History {...VIEW_ICON} /> },
    ].filter((option) => views.includes(option.value))} />
  );
  const workbench = (toolbar: ReactNode, content: ReactNode) => (
    <section aria-label="Workbench" className="grid min-w-0 grid-cols-[minmax(0,1fr)] content-start gap-5">
      <div className="flex flex-wrap items-center gap-3">{toolbar}</div>
      {content}
    </section>
  );
  // The workbench comes first in the document, so the keyboard meets the work
  // before the desk; wide screens place the desk to its right, narrow ones fold
  // it into a one-line strip above.
  const frame = (desk: ReactNode, main: ReactNode) => (
    <div className="grid grid-cols-[minmax(0,1fr)] items-start gap-6 lg:grid-cols-[minmax(0,1fr)_18.75rem]">
      <div className="min-w-0">{main}</div>
      {/* Stretched to the row so the desk inside can stay in view while the workbench scrolls. */}
      <div className="order-first lg:order-none lg:self-stretch">{desk}</div>
    </div>
  );

  if (!maintainer) {
    const readerView = view === "history" ? "systems" : view;
    return (
      <>
        {header}
        <CatalogueNav />
        <AsyncState
          status={asyncStatus(active)}
          loading={{ label: "Loading the catalogue", variant: "panel" }}
          error={{ title: "We couldn’t load the catalogue", message: errorMessage(active.error) }}
          onRetry={() => void active.refetch()}
          headingLevel="h2"
        >
          {active.data && frame(
            <ChangeDesk summary={<><span className="font-semibold">{versionName(active.data)}</span> <span className="text-meta text-ink-muted">· in use, read-only</span></>}>
              <LiveVersion current={active.data} />
              <p className="text-meta text-ink-muted m-0">
                Read-only. Changes are made by knowledge maintainers in a new version.
              </p>
            </ChangeDesk>,
            workbench(
              viewSwitch(["systems", "matrix", "domains", "products", "journeys"], readerView, (value) => update({ view: value })),
              <Landscape release={active.data} baseline={undefined} draft={undefined} organisation={organisation.data}
                view={readerView} heading="Systems in use" selected={system}
                onSelect={(id) => update({ system: id })} onOpenSystem={openSystem} />,
            ),
          )}
        </AsyncState>
      </>
    );
  }

  const drafts = (releases.data ?? []).filter((release) => release.status === "draft");
  const draft = drafts.find((release) => release.id === selected) ?? drafts[0];
  const current = active.data;
  const startButton = (
    <Button variant="primary" className="w-fit" icon={<Plus size={16} aria-hidden="true" />}
      onClick={() => { create.reset(); setNaming(true); }}>
      Start a new version
    </Button>
  );

  /** The page once the version in progress (if any) has handed over its desk and open step. */
  const layout = (draftDesk: ReactNode, workspace: ReactNode, pending: number, summary?: ReactNode) => {
    const onDraft = Boolean(draft) && showing === "draft";
    const stepOpen = onDraft && workspace !== null;
    const release = onDraft ? draft : current;
    const toolbar = (
      <>
        {draft && (view !== "history" || stepOpen) && (
          <Segmented<Showing> label="Version" value={onDraft ? "draft" : "active"}
            onChange={(value) => update({ version: value, step: null, view: view === "history" ? "systems" : view })}
            options={[
              { value: "active", name: `In use: ${current ? versionName(current) : "loading"}`, label: "In use" },
              { value: "draft", name: `In progress: ${versionName(draft)}${pending ? `, ${pending} suggestions waiting` : ""}`,
                label: <>In progress
                  {pending > 0 && <span className="bg-warning-wash text-warning text-meta rounded-full px-2 font-semibold tabular-nums">{pending}</span>}</> },
            ]} />
        )}
        {viewSwitch(["systems", "matrix", "domains", "products", "journeys", "history"], stepOpen ? null : view,
          (value) => update({ view: value, step: null }))}
      </>
    );
    const content = stepOpen ? (
      <div className="bg-surface border-line grid min-w-0 gap-5 rounded-md border border-solid p-6">
        <div className="border-line border-0 border-b border-solid pb-3">
          <Button size="sm" variant="ghost" icon={<ArrowLeft size={14} aria-hidden="true" />} onClick={() => openStep(null)}>
            Back to {view === "matrix" ? "dependencies" : view === "history" ? "history" : view === "domains" ? "domains"
              : view === "products" ? "product offerings" : view === "journeys" ? "journeys" : "systems"}
          </Button>
        </div>
        {workspace}
      </div>
    ) : view === "history" ? (
      <ReleaseHistory releases={releases.data ?? []} activeId={current?.id} onChanged={refresh}
        onRemoved={(removed) => {
          if (removed.id === draft?.id) setSelected(null);
          setNotice({ text: "The version in progress was removed.", tone: "neutral" });
        }} />
    ) : release ? (
      <Landscape release={release} baseline={onDraft ? current : undefined} draft={onDraft ? draft : undefined}
        organisation={organisation.data} view={view}
        heading={onDraft ? "Systems in this version" : "Systems in use"}
        selected={system} onSelect={(id) => update({ system: id })} onOpenSystem={openSystem} />
    ) : <LoadingState label="Loading the catalogue" variant="panel" />;

    return frame(
      <ChangeDesk collapseKey={step}
        summary={summary ?? <><span className="font-semibold">{current ? versionName(current) : "Catalogue"}</span> <span className="text-meta text-ink-muted">· in use · start a new version to change it</span></>}>
        <LiveVersion current={current} outdated={impact.data?.outdated_requirements} />
        {drafts.length > 1 && (
          <Select label="Version in progress" value={draft?.id}
            onChange={(event) => { setSelected(event.target.value); openStep(null); }}>
            {drafts.map((item) => (
              <option key={item.id} value={item.id}>{versionName(item)} · {item.systems.length} systems</option>
            ))}
          </Select>
        )}
        {draft ? draftDesk : (
          <section aria-labelledby="start-title" className="grid gap-3">
            <h2 className="text-title text-ink m-0" id="start-title">Change the catalogue</h2>
            <p className="text-meta text-ink-muted m-0">
              Changes go into a new version. Mapping keeps using the version in use until you publish.
            </p>
            {startButton}
          </section>
        )}
      </ChangeDesk>,
      workbench(toolbar, content),
    );
  };

  return (
    <>
      {header}
      <CatalogueNav />
      {naming && (
        <VersionNameDialog
          title="Start a new version"
          description="It starts as a copy of the version in use. Only one version can be in progress at a time."
          confirmLabel="Start version"
          saving={create.isPending}
          error={create.error ? errorMessage(create.error) : null}
          onSubmit={(name) => create.mutate(name)}
          onCancel={() => setNaming(false)}
        />
      )}
      {notice && (
        <p role="status"
          className={cx("text-body m-0 mb-4 flex items-center gap-2 rounded-md px-4 py-3",
            notice.tone === "success"
              ? "bg-success-wash text-ink border-0 border-l-[3px] border-solid border-l-[var(--success)]"
              : "text-ink-soft")}>
          {notice.tone === "success" && <CircleCheck className="text-success shrink-0" size={18} aria-hidden="true" />}
          <span>{notice.text}</span>
        </p>
      )}
      <AsyncState
        status={asyncStatus(releases)}
        loading={{ label: "Loading the catalogue", variant: "panel" }}
        error={{ title: "We couldn’t load the catalogue", message: errorMessage(releases.error) }}
        onRetry={() => void releases.refetch()}
        headingLevel="h2"
      >
        {draft ? (
          <DraftJourney
            key={draft.id}
            draft={draft}
            step={showing === "draft" ? step : null}
            onStep={openStep}
            onChanged={refresh}
            onPublished={() => {
              setNotice({ text: "Published. Requirement mapping now uses this version.", tone: "success" });
              setSelected(null); update({ step: null, version: "active", view: "systems" }); refresh();
            }}
            onDiscarded={() => {
              setNotice({ text: "The version in progress was removed.", tone: "neutral" });
              setSelected(null); update({ step: null }); refresh();
            }}
          >
            {({ desk, workspace, pending, summary }) => layout(desk, workspace, pending, summary)}
          </DraftJourney>
        ) : layout(null, null, 0)}
      </AsyncState>
    </>
  );
}
