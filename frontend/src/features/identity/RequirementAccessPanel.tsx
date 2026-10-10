import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { UserRoundPlus, X } from "lucide-react";
import { useState } from "react";

import { api, type RequirementAccess } from "../../api/client";
import { errorMessage, errorReference } from "../../api/errors";
import { queryKeys } from "../../app/queryKeys";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Disclosure } from "../../components/Disclosure";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Select } from "../../components/ui/Select";

/** The access history in words — never the enum with its underscores swapped out. */
const CHANGE_LABEL: Record<RequirementAccess["changes"][number]["kind"], string> = {
  claimed: "Claimed ownership",
  transferred: "Ownership transferred to",
  reviewer_assigned: "Reviewer added",
  reviewer_removed: "Reviewer removed",
};

function Person({ name, email }: { name: string; email?: string | null }) {
  return (
    <span className="grid min-w-0">
      <span className="text-body text-ink font-semibold">{name}</span>
      {email && <span className="text-meta text-ink-muted [overflow-wrap:anywhere]">{email}</span>}
    </span>
  );
}

export function RequirementAccessPanel({
  requirementId,
  access,
}: {
  requirementId: string;
  access: RequirementAccess;
}) {
  const queryClient = useQueryClient();
  const [selectedActor, setSelectedActor] = useState("");
  const [confirmTransfer, setConfirmTransfer] = useState(false);
  const actors = useQuery({ queryKey: queryKeys.scope("identity-actors"), queryFn: ({ signal }) => api.searchActors(undefined, undefined, { signal }) });
  const update = async (value: RequirementAccess) => {
    queryClient.setQueryData(queryKeys.assignments(requirementId), value);
    setSelectedActor("");
    await queryClient.invalidateQueries({ queryKey: queryKeys.requirementLists() });
  };
  const claim = useMutation({
    mutationFn: () => api.claimRequirementOwnership(requirementId, access.version),
    onSuccess: update,
  });
  const assign = useMutation({
    mutationFn: (actorId: string) => api.assignReviewer(requirementId, actorId, access.version),
    onSuccess: update,
  });
  const remove = useMutation({
    mutationFn: (actorId: string) => api.removeReviewer(requirementId, actorId, access.version),
    onSuccess: update,
  });
  const transfer = useMutation({
    mutationFn: (actorId: string) =>
      api.transferRequirementOwnership(requirementId, actorId, access.version),
    onSuccess: update,
  });
  const mutationError = claim.error ?? assign.error ?? remove.error ?? transfer.error;
  const unavailable = new Set([access.owner?.actor.id]);
  const choices = actors.data?.filter((actor) => !unavailable.has(actor.id)) ?? [];

  // Inside the People drawer, whose title names it: sections under that
  // heading, not a second bordered panel with its own kicker and title.
  return (
    <div className="grid gap-6">
      <section aria-labelledby="access-owner-title" className="grid gap-2">
        <h3 className="text-title text-ink m-0" id="access-owner-title">
          Owner
        </h3>
        {access.owner ? (
          <Person email={access.owner.actor.email} name={access.owner.actor.display_name} />
        ) : (
          <Card className="grid gap-3" padding="compact" tone="warning">
            <p className="text-body text-ink m-0 font-semibold">No owner is recorded for this requirement</p>
            <p className="text-body text-ink-soft m-0">
              It predates ownership. Claim it to confirm the analysis and manage reviewers.
            </p>
            {access.can_claim_owner && (
              <Button className="w-fit" disabled={claim.isPending} onClick={() => claim.mutate()} type="button" variant="primary">
                {claim.isPending ? "Claiming…" : "Claim ownership"}
              </Button>
            )}
          </Card>
        )}
      </section>

      <section aria-labelledby="access-reviewers-title" className="grid gap-2">
        <h3 className="text-title text-ink m-0" id="access-reviewers-title">
          Reviewers <span className="text-meta text-ink-muted font-normal tabular-nums">({access.reviewers.length})</span>
        </h3>
        {access.reviewers.length ? (
          <ul className="border-line m-0 grid list-none rounded-md border border-solid p-0">
            {access.reviewers.map((reviewer, index) => (
              <li
                className={`flex items-center justify-between gap-3 px-3 py-2 ${index > 0 ? "[border-top:1px_solid_var(--line)]" : ""}`}
                key={reviewer.actor.id}
              >
                <Person email={reviewer.actor.email} name={reviewer.actor.display_name} />
                {access.can_manage_assignments && (
                  <Button
                    aria-label={`Remove ${reviewer.actor.display_name}`}
                    icon={<X aria-hidden="true" size={16} />}
                    onClick={() => remove.mutate(reviewer.actor.id)}
                    size="icon"
                    type="button"
                    variant="ghost"
                  />
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-body text-ink-muted m-0">No reviewers yet.</p>
        )}
      </section>

      {access.can_manage_assignments ? (
        <section aria-labelledby="access-manage-title" className="grid gap-3">
          <h3 className="text-title text-ink m-0" id="access-manage-title">
            Add a reviewer or hand over
          </h3>
          <Select
            hint="People who have signed in at least once."
            label="Known actor"
            loading={actors.isPending}
            onChange={(event) => setSelectedActor(event.target.value)}
            value={selectedActor}
          >
            <option value="">Choose a person</option>
            {choices.map((actor) => (
              <option key={actor.id} value={actor.id}>
                {actor.display_name}
              </option>
            ))}
          </Select>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <Button
              disabled={!selectedActor || assign.isPending}
              icon={<UserRoundPlus aria-hidden="true" size={16} />}
              onClick={() => assign.mutate(selectedActor)}
              type="button"
              variant="secondary"
            >
              Add reviewer
            </Button>
            <Button disabled={!selectedActor || transfer.isPending} onClick={() => setConfirmTransfer(true)} variant="text">
              Transfer ownership
            </Button>
          </div>
        </section>
      ) : access.owner ? (
        <p className="text-body text-ink-muted m-0">
          Only {access.owner.actor.display_name}, the Requirement Owner, can manage reviewers or transfer ownership.
        </p>
      ) : null}
      {confirmTransfer && (
        <ConfirmDialog
          title="Transfer ownership?"
          message={`${choices.find((actor) => actor.id === selectedActor)?.display_name ?? "The selected actor"} becomes the Requirement Owner. You lose owner-only controls, including confirming the analysis and managing reviewers.`}
          confirmLabel="Transfer ownership"
          onCancel={() => setConfirmTransfer(false)}
          onConfirm={() => { setConfirmTransfer(false); transfer.mutate(selectedActor); }}
        />
      )}
      {mutationError && <ErrorNotice message={errorMessage(mutationError)} reference={errorReference(mutationError)} />}
      {access.changes.length > 0 && (
        <Disclosure label={`Access history (${access.changes.length})`}>
          <ol className="text-meta text-ink-soft m-0 grid gap-1.5 pl-5">
            {access.changes.map((change, index) => (
              <li key={`${change.recorded_at}-${index}`}>
                {CHANGE_LABEL[change.kind] ?? change.kind} {change.actor.display_name}
                <span className="text-ink-muted">
                  {" "}· by {change.performed_by.display_name},{" "}
                  <time dateTime={change.recorded_at}>
                    {new Date(change.recorded_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}
                  </time>
                </span>
              </li>
            ))}
          </ol>
        </Disclosure>
      )}
    </div>
  );
}
