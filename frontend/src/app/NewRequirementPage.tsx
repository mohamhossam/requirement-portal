import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { registerStartedJob } from "../features/jobs/jobObservation";
import { createStartKeys } from "../features/jobs/startKeys";
import { CircleAlert, CircleCheck, Clock, RotateCcw } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";

import {
  api,
  type Requirement,
  type RequirementDraft,
  type RequirementDraftInput,
} from "../api/client";
import { errorMessage, errorReference } from "../api/errors";
import { Disclosure } from "../components/Disclosure";
import { PageHeader } from "../components/shell";
import { ErrorState, LoadingState } from "../components/states";
import { DocumentPanel, type DocumentScope, type AttachmentState } from "../features/documents/DocumentPanel";
import { RequirementForm } from "../features/requirement/RequirementForm";
import { queryKeys } from "./queryKeys";
import { useDocumentTitle } from "./useDocumentTitle";
import { Button, ButtonLink, Card } from "../components/ui";
import { IntakeExample } from "../features/requirement/IntakeExample";

type CreateIntent = "primary" | "secondary";
type SaveState = "saved" | "saving" | "failed" | "unsaved";

const emptyDraft: RequirementDraftInput = {
  title: "",
  description: "",
  desired_outcome: "",
  customer_context: "",
  channels: [],
  systems: [],
  business_rules: [],
  constraints: [],
};

const fingerprint = (value: RequirementDraftInput) => JSON.stringify(value);

function inputFromDraft(draft: RequirementDraft): RequirementDraftInput {
  return {
    title: draft.title,
    description: draft.description,
    desired_outcome: draft.desired_outcome,
    customer_context: draft.customer_context,
    channels: draft.channels,
    systems: draft.systems,
    business_rules: draft.business_rules,
    constraints: draft.constraints,
  };
}

export function NewRequirementPage() {
  useDocumentTitle("New requirement");
  const navigate = useNavigate();
  const location = useLocation();
  // The Help menu's "Read the worked example" lands here with #example. A
  // client-side navigation scrolls nowhere by itself, and below `lg` the
  // example is a closed disclosure: open whichever copy is on screen and bring
  // it into view.
  useEffect(() => {
    if (location.hash !== "#example") return;
    const inline = document.getElementById("example-inline");
    const target = inline && inline.offsetParent !== null ? inline : document.getElementById("example");
    if (target instanceof HTMLDetailsElement) target.open = true;
    target?.scrollIntoView({ block: "start" });
  }, [location.hash, location.key]);
  const [searchParams] = useSearchParams();
  const requestedDraftId = searchParams.get("draft");
  const queryClient = useQueryClient();
  const [input, setInput] = useState<RequirementDraftInput | null>(null);
  const [createdDraft, setCreatedDraft] = useState<RequirementDraft | null>(null);
  const [saveState, setSaveState] = useState<SaveState>("saved");
  const [savedRequirement, setSavedRequirement] = useState<Requirement | null>(null);
  const [analysisFailure, setAnalysisFailure] = useState<string | null>(null);
  const lastSaved = useRef(fingerprint(emptyDraft));
  const [attachmentState, setAttachmentState] = useState<AttachmentState>({ hasIncludedAttachment: false, busy: false, blocked: false });
  const latestDraft = useRef<RequirementDraft | null>(null);
  const saveQueue = useRef<Promise<unknown>>(Promise.resolve());
  // Retrying after a lost response reuses its key, so the server replays the first start.
  const startKeys = useRef(createStartKeys()).current;

  const draftQuery = useQuery({
    queryKey: queryKeys.requirementDraft(requestedDraftId ?? "new"),
    queryFn: ({ signal }) => api.getRequirementDraft(requestedDraftId!, { signal }),
    enabled: Boolean(requestedDraftId),
    staleTime: Infinity,
  });
  const draft = createdDraft ?? draftQuery.data ?? null;
  useEffect(() => {
    if (draft && (!latestDraft.current || latestDraft.current.version < draft.version)) latestDraft.current = draft;
  }, [draft]);

  const persistDraft = (value: RequirementDraftInput): Promise<RequirementDraft> => {
    const save = saveQueue.current.then(async () => {
      const current = latestDraft.current;
      if (current && fingerprint(value) === lastSaved.current) return current;
      const saved = current ? await api.saveRequirementDraft(current.id, value, current.version)
        : await api.createRequirementDraft(value);
      latestDraft.current = saved;
      lastSaved.current = fingerprint(value);
      setCreatedDraft(saved);
      queryClient.setQueryData(queryKeys.requirementDraft(saved.id), saved);
      return saved;
    });
    saveQueue.current = save.catch(() => undefined);
    return save;
  };

  useEffect(() => {
    if (!draftQuery.data) return;
    lastSaved.current = fingerprint(inputFromDraft(draftQuery.data));
  }, [draftQuery.data]);

  const autosave = useMutation({
    // The draft has its own four-state save indicator; a toast per debounced
    // save would be relentless.
    meta: { toastOnError: false },
    mutationFn: ({ value }: { value: RequirementDraftInput; version: number | null }) => {
      setSaveState("saving");
      return persistDraft(value);
    },
    onSuccess: (saved, variables) => {
      lastSaved.current = fingerprint(variables.value);
      setSaveState("saved");
      setCreatedDraft(saved);
      queryClient.setQueryData(queryKeys.requirementDraft(saved.id), saved);
      void queryClient.invalidateQueries({ queryKey: queryKeys.requirementDrafts() });
    },
    onError: () => setSaveState("failed"),
  });

  useEffect(() => {
    if (
      !input ||
      autosave.isPending || attachmentState.busy ||
      saveState === "failed" ||
      fingerprint(input) === lastSaved.current
    ) return;
    const timer = window.setTimeout(
      () => autosave.mutate({ value: input, version: draft?.version ?? null }),
      700,
    );
    return () => window.clearTimeout(timer);
  }, [autosave, draft, input, saveState, attachmentState.busy]);

  const remember = async (requirement: Requirement, promotedDraftId: string) => {
    localStorage.setItem("lastRequirementId", requirement.id);
    await queryClient.invalidateQueries({ queryKey: queryKeys.requirementLists() });
    await queryClient.invalidateQueries({ queryKey: queryKeys.requirementDrafts() });
    queryClient.removeQueries({ queryKey: queryKeys.requirementDraft(promotedDraftId) });
  };

  const startAnalysis = async (requirementId: string, contextToken: string) => {
    const input = { operation: "analyse_requirement", context_token: contextToken, force: false } as const;
    try {
      const job = await api.startAiJob(requirementId, input, startKeys.keyFor(input));
      startKeys.settle(input);
      return job;
    } catch (error) {
      startKeys.settle(input, error);
      throw error;
    }
  };

  const submit = useMutation({
    mutationFn: async ({ value, intent }: { value: RequirementDraftInput; intent: CreateIntent }) => {
      const saved = await persistDraft(value);
      if (intent === "secondary") return { requirement: null, analysisFailure: null };
      const promoted = await api.promoteRequirementDraft(saved.id, saved.version);
      const requirement = promoted.analysis_context_token
        ? promoted
        : await api.getRequirement(promoted.id);
      await remember(requirement, saved.id);
      setSavedRequirement(requirement);
      try {
        if (!requirement.analysis_context_token) {
          throw new Error("The analysis context is unavailable. Reload the Requirement and retry.");
        }
        const job = await startAnalysis(requirement.id, requirement.analysis_context_token);
        registerStartedJob(queryClient, requirement.id, job);
        return {
          requirement,
          analysisFailure: null,
          destination: `/requirements/${requirement.id}/clarify`,
        };
      } catch (failure) {
        return { requirement, analysisFailure: errorMessage(failure), destination: null };
      }
    },
    onSuccess: (result) => {
      if (!result.requirement) {
        navigate("/");
      } else if (result.analysisFailure) {
        setAnalysisFailure(result.analysisFailure);
      } else if (result.destination) {
        navigate(result.destination);
      }
    },
  });

  const retryAnalysis = useMutation({
    mutationFn: async () => {
      if (!savedRequirement) return;
      // Always re-read: the token held since creation may be stale by now.
      const requirement = await api.getRequirement(savedRequirement.id);
      setSavedRequirement(requirement);
      if (!requirement.analysis_context_token) {
        throw new Error("The analysis context is unavailable. Reload the Requirement and retry.");
      }
      const job = await startAnalysis(requirement.id, requirement.analysis_context_token);
      registerStartedJob(queryClient, requirement.id, job);
    },
    onSuccess: () => savedRequirement && navigate(`/requirements/${savedRequirement.id}/clarify`),
    onError: (failure) => setAnalysisFailure(errorMessage(failure)),
  });

  const retrySave = () => {
    if (input) {
      autosave.mutate({ value: input, version: draft?.version ?? null });
    }
  };
  const busy = submit.isPending;
  const currentInput = input ?? (draft ? inputFromDraft(draft) : emptyDraft);
  const prepareDocumentScope = async (): Promise<DocumentScope> => {
    const saved = await persistDraft(currentInput);
    lastSaved.current = fingerprint(currentInput);
    setSaveState("saved");
    setCreatedDraft(saved);
    queryClient.setQueryData(queryKeys.requirementDraft(saved.id), saved);
    return { kind: "draft", id: saved.id };
  };
  const noTitle = !currentInput.title.trim();
  const noNeed = !currentInput.description.trim() && !attachmentState.hasIncludedAttachment;
  const ready = !noTitle && !noNeed && !attachmentState.blocked && !attachmentState.busy;
  // One readiness line, beside the button it gates. It used to be a card below
  // the action bar reading "Missing: title, business need text or a ready
  // attachment", always edged in indigo, including when it meant "not ready".
  const readinessText = attachmentState.busy
    ? "Files are still processing. Analysis can start when they finish."
    : attachmentState.blocked
      ? "A file could not be read. Retry it, or leave it out of analysis."
      : noTitle && noNeed
        ? "Add a title and describe the need."
        : noTitle
          ? "Add a title."
          : noNeed
            ? "Describe the need, or attach a file and include it in analysis."
            : null;
  const readiness = (
    <p className="text-body m-0 flex items-start gap-1.5" id="intake-readiness" aria-live="polite">
      {ready
        ? <CircleCheck className="text-success mt-0.5 shrink-0" size={16} aria-hidden="true" />
        : attachmentState.busy
          ? <Clock className="text-ink-muted mt-0.5 shrink-0" size={16} aria-hidden="true" />
          : <CircleAlert className="text-warning mt-0.5 shrink-0" size={16} aria-hidden="true" />}
      <span>
        <strong className="text-ink">{ready ? "Ready for analysis" : "Not ready for analysis"}</strong>
        {readinessText && <span className="text-ink-soft"> · {readinessText}</span>}
      </span>
    </p>
  );
  const savedAt = draft ? savedLabel(draft.updated_at) : null;
  const saveText = saveState === "saving"
    ? "Saving draft…"
    : saveState === "failed"
      ? "Draft save failed. What you typed is still here."
      : saveState === "unsaved"
        ? "Your changes save automatically."
        : savedAt ?? "Not saved yet. Your draft saves as you type.";
  const status = (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
      {/* Only a failure is announced. "Saving draft…" then "Saved 15:04" on
          every pause in typing was a running commentary nobody asked for. */}
      <p className={saveState === "failed" ? "text-meta text-danger m-0" : "text-meta text-ink-muted m-0"} role={saveState === "failed" ? "alert" : undefined}>
        {saveText}
      </p>
      {saveState === "failed" && (
        <Button variant="text" onClick={retrySave} icon={<RotateCcw size={14} aria-hidden="true" />}>Retry save</Button>
      )}
    </div>
  );

  return (
    <div>
      <PageHeader
        title="New requirement"
        description="Describe what you need in your own words. Only a title and the need itself are required, and your draft saves as you go."
      />

      {savedRequirement && analysisFailure ? (
        <Card as="section" tone="warning" aria-labelledby="saved-title" className="grid max-w-[52rem] gap-3">
          <h2 className="text-headline text-ink m-0" id="saved-title">Your requirement is saved. Nothing was lost.</h2>
          <p className="text-body text-ink-soft m-0">Analysis could not start: {analysisFailure}</p>
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="primary" loading={retryAnalysis.isPending} loadingLabel="Retrying analysis…" onClick={() => retryAnalysis.mutate()}>Retry analysis</Button>
            <ButtonLink variant="secondary" to={`/requirements/${savedRequirement.id}/capture`}>Open saved requirement</ButtonLink>
          </div>
        </Card>
      ) : requestedDraftId && draftQuery.isPending ? (
        <LoadingState label="Opening your draft" />
      ) : draftQuery.isError ? (
        <ErrorState
          headingLevel="h2"
          title="We couldn’t open that draft"
          message={errorMessage(draftQuery.error)}
          reference={errorReference(draftQuery.error)}
          onRetry={() => void draftQuery.refetch()}
        />
      ) : (
        // The example beside the form, not below it: it used to sit after the
        // form and its save buttons, where the owner met it after writing, or
        // never (ux-plan §3.12). At `lg` it fills the column the 52rem form
        // left empty; below that the form carries it under the business need.
        <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,52rem)_minmax(16rem,22rem)]">
          <section className="min-w-0" aria-label="Requirement details">
            <RequirementForm
              key={`draft-form-${requestedDraftId ?? "new"}`}
              context="create"
              initial={currentInput}
              submitLabel="Save and analyse"
              secondarySubmitLabel="Save draft and exit"
              busy={busy}
              error={submit.error ? errorMessage(submit.error) : null}
              onChange={(value) => { setInput(value); setSaveState("unsaved"); }}
              onSubmit={(value, intent) => submit.mutate({ value, intent })}
              hasIncludedAttachment={attachmentState.hasIncludedAttachment}
              attachmentsBusy={attachmentState.busy}
              attachmentsBlocked={attachmentState.blocked}
              attachments={<DocumentPanel businessNeed headingLevel="h2"
                scope={draft ? { kind: "draft", id: draft.id } : null}
                prepareScope={prepareDocumentScope} onStateChange={setAttachmentState} />}
              readiness={readiness}
              readinessId="intake-readiness"
              status={status}
              example={
                <Disclosure className="lg:hidden" defaultOpen={location.hash === "#example"} id="example-inline" label="See an example">
                  {/* Framed, so its labels cannot be mistaken for the form's own. */}
                  <div className="border-line bg-surface-sunken rounded-md border border-solid p-4">
                    <IntakeExample />
                  </div>
                </Disclosure>
              }
            />
          </section>
          <aside
            aria-labelledby="example-title"
            // Scrolls within itself on a short screen, so its closing note —
            // what happens after saving — never sits below the fold.
            className="border-line bg-surface-sunken hidden rounded-md border border-solid p-5 lg:sticky lg:top-[calc(var(--header-height)+var(--space-6))] lg:block lg:max-h-[calc(100dvh-var(--header-height)-var(--space-12))] lg:overflow-y-auto"
            // The Help menu links here ("Read the worked example").
            id="example"
          >
            <IntakeExample headingId="example-title" />
          </aside>
        </div>
      )}
    </div>
  );
}

const TIME = new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit" });
const DAY_AND_TIME = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

/** "Saved 15:03" today; with the date on a draft resumed another day. */
function savedLabel(iso: string): string {
  const when = new Date(iso);
  const today = new Date();
  const sameDay = when.toDateString() === today.toDateString();
  return `Saved ${sameDay ? TIME.format(when) : DAY_AND_TIME.format(when)}`;
}
