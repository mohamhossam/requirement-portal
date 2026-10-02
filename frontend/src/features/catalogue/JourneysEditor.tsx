import { useMutation } from "@tanstack/react-query";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { errorMessage } from "../../api/errors";
import { knowledgeApi, type Journey, type KnowledgeRelease } from "../../api/knowledge";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Button } from "../../components/ui";
import { JourneyDrawer } from "./JourneyDrawer";

const EMPTY: Journey = { id: "", name: "", activities: [], flow_rules: [], integrations: [], edges: [] };

const plural = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`;

/**
 * The version's journeys (ADR-0096), added and edited by hand. Each opens in
 * a drawer; removing one asks first, since its activities and rules go with it.
 */
export function JourneysEditor({ draft, onChanged }: { draft: KnowledgeRelease; onChanged: () => void }) {
  const journeys = draft.journeys ?? [];
  const offerings = draft.products ?? [];
  const [editing, setEditing] = useState<{ journey: Journey; creating: boolean } | null>(null);
  const [removing, setRemoving] = useState<Journey | null>(null);
  const [status, setStatus] = useState("");
  const save = useMutation({
    mutationFn: knowledgeApi.save,
    onSuccess: () => {
      setEditing(null);
      setRemoving(null);
      onChanged();
    },
  });
  const saveJourneys = (next: Journey[], done: string) =>
    save.mutate({ ...draft, journeys: next }, { onSuccess: () => setStatus(done) });
  const systems = [...draft.systems].sort((a, b) => a.name.localeCompare(b.name))
    .map((system) => ({ id: system.id, name: system.name }));

  return (
    <section className="grid min-w-0 gap-3" aria-labelledby="journeys-editor-title">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="grid gap-1">
          <h4 className="text-body text-ink m-0 font-semibold" id="journeys-editor-title" tabIndex={-1}>
            Journeys ({journeys.length})
          </h4>
          <p className="text-meta text-ink-muted m-0 max-w-[68ch]">
            The activities that fulfil an offering's orders, the systems that perform them, and the rules for
            exceptions and side tracks.
          </p>
        </div>
        <Button icon={<Plus size={16} aria-hidden="true" />}
          onClick={() => { save.reset(); setEditing({ journey: EMPTY, creating: true }); }}>
          Add journey
        </Button>
      </header>
      {save.error && !editing && <ErrorNotice message={errorMessage(save.error)} />}
      {status && <p className="text-meta text-ink-soft m-0" role="status">{status}</p>}
      {journeys.length === 0 ? (
        <p className="text-body text-ink-muted m-0">No journeys yet.</p>
      ) : (
        <ul role="list" className="border-line m-0 grid list-none rounded-md border border-solid p-0 [&>li+li]:[border-top:1px_solid_var(--line)]">
          {[...journeys].sort((a, b) => a.name.localeCompare(b.name)).map((journey) => {
            const offering = offerings.find((item) => item.id === journey.product_id);
            return (
              <li key={journey.id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
                <span className="grid min-w-0 flex-1 gap-0.5">
                  <span className="text-body text-ink">
                    {journey.name}
                    {offering && <span className="text-meta text-ink-muted"> · {offering.name}</span>}
                  </span>
                  <span className="text-meta text-ink-muted">
                    {[plural((journey.activities ?? []).length, "activity", "activities"),
                      plural((journey.flow_rules ?? []).length, "rule", "rules"),
                      plural((journey.integrations ?? []).length, "integration", "integrations")].join(" · ")}
                  </span>
                </span>
                <span className="flex flex-wrap gap-1">
                  <Button size="sm" variant="ghost" icon={<Pencil size={14} aria-hidden="true" />}
                    aria-label={`Edit ${journey.name}`}
                    onClick={() => { save.reset(); setEditing({ journey, creating: false }); }}>
                    Edit
                  </Button>
                  <Button size="sm" variant="ghost" icon={<Trash2 size={14} aria-hidden="true" />}
                    disabled={save.isPending} aria-label={`Remove ${journey.name}`}
                    onClick={() => setRemoving(journey)}>
                    Remove
                  </Button>
                </span>
              </li>
            );
          })}
        </ul>
      )}
      {editing && (
        <JourneyDrawer
          initial={editing.journey}
          systems={systems}
          offerings={offerings}
          taken={journeys.map((item) => item.id)}
          creating={editing.creating}
          saving={save.isPending}
          error={save.error ? errorMessage(save.error) : null}
          onSave={(journey) => saveJourneys(editing.creating
            ? [...journeys, journey]
            : journeys.map((item) => (item.id === journey.id ? journey : item)),
          `${editing.creating ? "Added" : "Saved"} ${journey.name}.`)}
          onCancel={() => setEditing(null)}
        />
      )}
      {removing && (
        <ConfirmDialog
          title={`Remove ${removing.name}?`}
          message="Its activities, rules and integrations are removed from this version too."
          confirmLabel="Remove journey"
          onCancel={() => setRemoving(null)}
          onConfirm={() => saveJourneys(journeys.filter((item) => item.id !== removing.id), `Removed ${removing.name}.`)}
        />
      )}
    </section>
  );
}
