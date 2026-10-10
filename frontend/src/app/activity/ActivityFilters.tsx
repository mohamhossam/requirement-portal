import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import { api, type ActivityAction, type ActivityCategory } from "../../api/client";
import { Combobox, type ComboboxOption } from "../../components/ui/Combobox";
import { Input } from "../../components/ui/Input";
import { Select } from "../../components/ui/Select";
import { queryKeys } from "../queryKeys";
import { actionLabels, actionsByCategory, anyCategoryLabels, categoryLabels, dateRangeError } from "./labels";

/** What the filters read from, and write to, the URL. */
export type ActivityFilterState = {
  requirementId: string;
  actorId: string;
  category: ActivityCategory | null;
  action: ActivityAction | null;
  /** YYYY-MM-DD, a UTC day. */
  start: string;
  end: string;
};

export type ActivityFilterChange =
  | { key: "requirement"; value: string }
  | { key: "actor"; value: string }
  | { key: "what"; category: ActivityCategory | null; action: ActivityAction | null }
  | { key: "start" | "end"; value: string };

/** A pause after the last keystroke before the directory is asked. */
function useSettled(value: string, delay = 250) {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setSettled(value.trim()), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return settled;
}

const shortId = (id: string) => id.slice(0, 8);

/** Native date fields draw their own picker button; give it the system ring. */
const DATE_FIELD = "[&::-webkit-calendar-picker-indicator:focus-visible]:[outline:3px_solid_var(--focus)]";

/**
 * Four questions, in the order an auditor asks them: which requirement, who,
 * what kind of thing, and when (docs/ux-plan.md §3.8). Requirement and person
 * are searched by name — the IDs they used to ask for never have to be known —
 * and Category and Action are one control, the action listed under its
 * category, so the thirty actions never face anyone as a flat list.
 */
export function ActivityFilters({
  state,
  onChange,
  knownActors,
  knownRequirements,
}: {
  state: ActivityFilterState;
  onChange: (change: ActivityFilterChange) => void;
  /** People already on screen, so a chosen person keeps their name. */
  knownActors: Map<string, string>;
  knownRequirements: Map<string, string>;
}) {
  const [requirementQuery, setRequirementQuery] = useState("");
  const [actorQuery, setActorQuery] = useState("");
  const requirementSearch = useSettled(requirementQuery);
  const actorSearch = useSettled(actorQuery);

  const requirementOptions = useQuery({
    queryKey: queryKeys.scope("activity-requirement-options", requirementSearch),
    queryFn: ({ signal }) => api.listRequirements({ q: requirementSearch || undefined, limit: 8 }, { signal }),
  });
  const actorOptions = useQuery({
    queryKey: queryKeys.scope("activity-actor-options", actorSearch),
    queryFn: ({ signal }) => api.searchActors(actorSearch, 8, { signal }),
  });
  // A link can arrive holding only an ID; find the name it stands for.
  const chosenRequirement = useQuery({
    queryKey: queryKeys.scope("activity-requirement", state.requirementId),
    queryFn: ({ signal }) => api.listRequirements({ q: state.requirementId, limit: 5 }, { signal }),
    enabled: Boolean(state.requirementId) && !knownRequirements.has(state.requirementId),
  });

  const requirements = useMemo<ComboboxOption[]>(
    () =>
      (requirementOptions.data?.requirements ?? []).map((item) => ({
        id: item.id,
        label: item.title,
        meta: <span className="font-mono">{shortId(item.id)}</span>,
      })),
    [requirementOptions.data],
  );
  const actors = useMemo<ComboboxOption[]>(
    () =>
      (actorOptions.data ?? []).map((actor) => ({
        id: actor.id,
        label: actor.display_name,
        meta: actor.email ?? undefined,
      })),
    [actorOptions.data],
  );

  const requirementName =
    knownRequirements.get(state.requirementId) ??
    chosenRequirement.data?.requirements.find((item) => item.id === state.requirementId)?.title ??
    `Requirement ${shortId(state.requirementId)}`;
  const actorName =
    knownActors.get(state.actorId) ??
    actorOptions.data?.find((actor) => actor.id === state.actorId)?.display_name ??
    "Selected person";

  const what = state.action ? `action:${state.action}` : state.category ? `category:${state.category}` : "";
  const rangeError = dateRangeError(state);

  return (
    <div className="grid items-start gap-x-3 gap-y-4 md:grid-cols-2 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_minmax(0,1.2fr)_auto]">
      <Combobox
        emptyText="No requirement matches that name or ID"
        label="Requirement"
        loading={requirementOptions.isFetching}
        onQueryChange={setRequirementQuery}
        onSelect={(option) => onChange({ key: "requirement", value: option?.id ?? "" })}
        options={requirements}
        placeholder="Any requirement"
        query={requirementQuery}
        selected={state.requirementId ? { id: state.requirementId, label: requirementName } : null}
      />
      <Combobox
        emptyText="No one matches that name or email"
        label="Person"
        loading={actorOptions.isFetching}
        onQueryChange={setActorQuery}
        onSelect={(option) => onChange({ key: "actor", value: option?.id ?? "" })}
        options={actors}
        placeholder="Anyone"
        query={actorQuery}
        selected={state.actorId ? { id: state.actorId, label: actorName } : null}
      />
      <Select
        label="What happened"
        onChange={(event) => {
          const [kind, value] = event.target.value.split(":");
          if (kind === "action") {
            const group = actionsByCategory.find((entry) => entry.actions.includes(value as ActivityAction));
            onChange({ key: "what", category: group?.category ?? null, action: value as ActivityAction });
          } else {
            onChange({ key: "what", category: kind === "category" ? (value as ActivityCategory) : null, action: null });
          }
        }}
        value={what}
      >
        <option value="">Anything</option>
        {actionsByCategory.map(({ category, actions }) => (
          <optgroup key={category} label={categoryLabels[category]}>
            <option value={`category:${category}`}>{anyCategoryLabels[category]}</option>
            {actions.map((action) => (
              <option key={action} value={`action:${action}`}>
                {actionLabels[action]}
              </option>
            ))}
          </optgroup>
        ))}
      </Select>
      {/* Two fields that answer one question, so they are one group — and each
          keeps its own visible label, level with the other three. */}
      <fieldset className="m-0 grid min-w-0 grid-cols-2 gap-2 border-0 p-0 md:col-span-2 lg:col-span-1 lg:w-[19rem]">
        <legend className="sr-only">When</legend>
        <Input
          className={DATE_FIELD}
          label="From"
          max={state.end || undefined}
          onChange={(event) => onChange({ key: "start", value: event.target.value })}
          type="date"
          value={state.start}
        />
        <Input
          className={DATE_FIELD}
          error={rangeError}
          label="Before"
          min={state.start || undefined}
          onChange={(event) => onChange({ key: "end", value: event.target.value })}
          type="date"
          value={state.end}
        />
      </fieldset>
    </div>
  );
}
