import { useState } from "react";

import type {
  ProductImpactDecision,
  ProductVerdict,
  RequirementAnalysis,
} from "../../api/client";
import { changeTypeLabel, systemRoleLabel } from "../architecture/labels";
import { Badge, Button, Card, Select, Textarea } from "../../components/ui";
import { PRODUCT_DECISION_LABEL, VERDICT_LABEL } from "./labels";

export type ProductImpactChoice = {
  decision: ProductImpactDecision;
  verdict?: ProductVerdict;
  rationale?: string;
};

const VERDICTS = Object.keys(VERDICT_LABEL) as ProductVerdict[];

/**
 * Where this requirement sits in the product portfolio (ADR-0115).
 *
 * The knowledge portal suggests a verdict from the analysed facts; the
 * Requirement Owner accepts it, overrides it with a reason, or marks it
 * unknown. Confirmation waits for one of the three, because generation and
 * publication read only the decision (ADR-0116). Until the live gate has
 * proven the suggestions (`verdict_validated`), the card calls the verdict a
 * suggestion and says so.
 */
export function ProductImpactCard({
  analysis,
  busy,
  canDecide,
  permissionReason,
  onDecide,
}: {
  analysis: RequirementAnalysis;
  busy: boolean;
  canDecide: boolean;
  permissionReason?: string;
  onDecide?: (choice: ProductImpactChoice) => void;
}) {
  const impact = analysis.product_impact;
  const [overriding, setOverriding] = useState(false);
  const [changing, setChanging] = useState(false);
  const [verdict, setVerdict] = useState<ProductVerdict | "">("");
  const [rationale, setRationale] = useState("");

  if (analysis.product_impact_status === "unavailable" && !impact) {
    return (
      <Card tone="warning" role="status" aria-label="Product impact not assessed">
        <h3 className="text-label text-ink m-0">Product impact was not assessed</h3>
        <p className="text-body text-ink m-0 mt-1">
          The knowledge portal could not be reached when this analysis ran. Send an answer or
          start a new analysis to ask it again.
        </p>
      </Card>
    );
  }
  if (!impact) return null;

  const editable = !analysis.human_confirmed && (!impact.decision || changing);
  const suggested = impact.suggested_verdict;
  const covered = impact.needs.filter((need) => need.covered).length;
  const owners = new Map(impact.owners.map((owner) => [owner.system_id, owner]));
  const otherVerdicts = VERDICTS.filter((item) => item !== suggested);
  const decide = (choice: ProductImpactChoice) => {
    onDecide?.(choice);
    setOverriding(false);
    setChanging(false);
    setVerdict("");
    setRationale("");
  };

  return (
    <Card
      aria-labelledby="product-impact-heading"
      className="grid gap-3 p-4"
      tone={impact.decision ? "default" : "warning"}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id="product-impact-heading" className="text-title text-ink m-0">Product impact</h3>
        {impact.decision ? (
          <Badge tone="success">{PRODUCT_DECISION_LABEL[impact.decision]}</Badge>
        ) : (
          <Badge tone="warning">Awaiting your decision</Badge>
        )}
      </div>

      {analysis.product_impact_status === "unavailable" && (
        <p className="text-body text-ink-soft m-0" role="status">
          The knowledge portal could not be reached on the last round, so this is the earlier
          assessment.
        </p>
      )}

      <div className="grid gap-1">
        <span className="text-label text-ink-muted">
          {impact.decision && impact.decision !== "accepted" ? "Your verdict" : "Suggested verdict"}
        </span>
        <p className="text-document-lead text-ink m-0 font-serif">
          {impact.decision
            ? impact.verdict ? VERDICT_LABEL[impact.verdict] : "Not known yet"
            : suggested ? VERDICT_LABEL[suggested] : "No verdict yet: the catalogue needs answers first"}
        </p>
        {!impact.verdict_validated && suggested && (
          <p className="text-meta text-ink-muted m-0">
            A suggestion. Its accuracy has not been proven on real requirements yet, so check it.
          </p>
        )}
        {impact.decision === "overridden" && suggested && (
          <p className="text-meta text-ink-muted m-0">Suggested: {VERDICT_LABEL[suggested]}</p>
        )}
      </div>

      {impact.reason && <p className="text-body text-ink-soft m-0 max-w-[68ch]">{impact.reason}</p>}

      <dl className="text-body m-0 grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1">
        {(impact.offering_name || impact.offering_id) && <>
          <dt className="text-ink-muted">Offering</dt>
          <dd className="text-ink m-0">{impact.offering_name ?? impact.offering_id}</dd>
        </>}
        {impact.needs.length > 0 && <>
          <dt className="text-ink-muted">Coverage</dt>
          <dd className="text-ink m-0 tabular-nums">
            {covered} of {impact.needs.length} capabilities already covered
          </dd>
        </>}
        {impact.proposal && <>
          <dt className="text-ink-muted">Proposal</dt>
          <dd className="text-ink m-0">{impact.proposal}</dd>
        </>}
        {impact.new_values.length > 0 && <>
          <dt className="text-ink-muted">New in the catalogue</dt>
          <dd className="text-ink m-0">{impact.new_values.join(", ")}</dd>
        </>}
      </dl>

      {impact.needs.length > 0 && (
        <section aria-label="Capabilities needed" className="grid gap-1.5">
          <h4 className="text-label text-ink-muted m-0">Capabilities needed</h4>
          <ul role="list" className="m-0 grid list-none gap-1 p-0">
            {impact.needs.map((need) => (
              <li key={need.concept_id} className="text-body text-ink-soft flex flex-wrap items-center gap-2">
                <span className="text-ink">{need.label}</span>
                <span className="text-meta text-ink-muted">{need.path}</span>
                {need.covered ? <Badge tone="success">Covered</Badge> : <Badge tone="warning">Not covered</Badge>}
                {need.weak && <Badge tone="neutral">Weak link: check it</Badge>}
              </li>
            ))}
          </ul>
        </section>
      )}

      {impact.gaps.length > 0 && (
        <section aria-label="Gaps" className="grid gap-1.5">
          <h4 className="text-label text-ink-muted m-0">Gaps for an architect</h4>
          <ul className="text-body text-ink-soft m-0 grid gap-1 pl-5">
            {impact.gaps.map((gap) => (
              <li key={`${gap.kind}-${gap.concept_id}-${gap.system_id ?? ""}`}>
                <strong className="text-ink">{gap.label}</strong>: {gap.reason}
              </li>
            ))}
          </ul>
        </section>
      )}

      {impact.systems.length > 0 && (
        <section aria-label="Systems affected" className="grid gap-1.5">
          <h4 className="text-label text-ink-muted m-0">Systems affected</h4>
          <ul role="list" className="m-0 grid list-none gap-2 p-0">
            {impact.systems.map((system) => {
              const owner = owners.get(system.id);
              const path = system.paths[0];
              return (
                <li key={system.id} className="border-line bg-surface-sunken grid gap-1 rounded-md border border-solid p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <strong className="text-body text-ink font-semibold">{system.name}</strong>
                    <Badge tone="neutral">{systemRoleLabel(system.role)}</Badge>
                    <Badge tone="neutral">{changeTypeLabel(system.change_type)}</Badge>
                  </div>
                  {path && path.length > 0 && (
                    <p className="text-meta text-ink-muted m-0">
                      <span className="sr-only">Why: </span>
                      {path.map((step) => step.label || step.id).join(" › ")}
                    </p>
                  )}
                  {owner && (
                    <p className="text-meta text-ink-soft m-0">
                      {owner.squads.length ? owner.squads.join(", ") : "No squad assigned"}
                      {owner.people.length > 0 && ` · ${owner.people.join(", ")}`}
                      {owner.open_seats > 0 &&
                        ` · ${owner.open_seats} open seat${owner.open_seats === 1 ? "" : "s"}`}
                    </p>
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      )}

      {impact.questions.length > 0 && !impact.decision && (
        <p className="text-body text-ink-soft m-0">
          The catalogue asked {impact.questions.length} question{impact.questions.length === 1 ? "" : "s"}{" "}
          to place this requirement. {impact.questions.length === 1 ? "It is" : "They are"} with the
          questions to answer first.
        </p>
      )}
      {impact.uncertainty && (
        <p className="text-body text-ink-soft m-0"><strong className="text-ink">Not certain:</strong> {impact.uncertainty}</p>
      )}

      {editable && (
        <div className="grid gap-3">
          <div className="flex flex-wrap gap-2">
            <Button
              blockedReason={canDecide ? (suggested ? undefined : "There is no suggested verdict to accept.") : permissionReason}
              disabled={busy || !canDecide || !suggested}
              onClick={() => decide({ decision: "accepted" })}
              variant="primary"
            >
              Accept the suggestion
            </Button>
            <Button
              aria-expanded={overriding}
              disabled={busy || !canDecide}
              onClick={() => setOverriding((value) => !value)}
            >
              Choose another verdict
            </Button>
            <Button
              disabled={busy || !canDecide}
              onClick={() => decide({ decision: "unknown" })}
              variant="ghost"
            >
              Mark as unknown
            </Button>
            {changing && (
              <Button disabled={busy} onClick={() => setChanging(false)} variant="text">
                Cancel
              </Button>
            )}
          </div>
          {overriding && (
            <form
              className="border-line grid gap-3 rounded-md border border-dashed p-3"
              onSubmit={(event) => {
                event.preventDefault();
                if (verdict && rationale.trim()) {
                  decide({ decision: "overridden", verdict, rationale: rationale.trim() });
                }
              }}
            >
              <Select
                label="Verdict"
                onChange={(event) => setVerdict(event.target.value as ProductVerdict | "")}
                value={verdict}
              >
                <option value="">Choose a verdict</option>
                {otherVerdicts.map((item) => (
                  <option key={item} value={item}>{VERDICT_LABEL[item]}</option>
                ))}
              </Select>
              <Textarea
                hint="Required. It stays with the decision for reviewers."
                label="Why the suggestion is wrong"
                maxLength={2000}
                onChange={(event) => setRationale(event.target.value)}
                rows={2}
                value={rationale}
              />
              <div>
                <Button disabled={busy || !verdict || !rationale.trim()} type="submit">
                  Save this verdict
                </Button>
              </div>
            </form>
          )}
        </div>
      )}

      {impact.decision && !editable && (
        <div className="grid gap-1">
          <p className="text-meta text-ink-muted m-0">
            Decided by {impact.decided_by?.display_name ?? "a reviewer"}.
            {impact.rationale && <> Reason: <bdi>{impact.rationale}</bdi></>}
          </p>
          {!analysis.human_confirmed && (
            <div>
              <Button
                blockedReason={canDecide ? undefined : permissionReason}
                disabled={busy}
                onClick={() => setChanging(true)}
                size="sm"
                variant="text"
              >
                Change this decision
              </Button>
            </div>
          )}
        </div>
      )}

      <p className="text-meta text-ink-muted m-0">
        Catalogue <span className="font-mono">{impact.release_id}</span>
        {impact.model ? ` · ${impact.model}` : ""}
      </p>
    </Card>
  );
}
