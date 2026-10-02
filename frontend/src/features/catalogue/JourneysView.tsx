import type { CatalogueDiff, Journey, KnowledgeRelease, SourceConfidence } from "../../api/knowledge";
import {
  Badge, Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow, cx,
} from "../../components/ui";
import { FOCUS_RING } from "../../components/ui/recipes";
import { JourneyFlow } from "./JourneyFlow";
import { CHANGE_LABEL, CONFIDENCE_LABEL, RULE_LABEL, byNumber, roleLabel } from "./labels";

const SYSTEM_LINK = cx(
  "text-body text-ink-soft hover:text-ink inline min-h-6 cursor-pointer border-0 bg-transparent p-0 text-left underline underline-offset-2",
  FOCUS_RING,
);

function Confidence({ value }: { value: SourceConfidence | null | undefined }) {
  if (!value) return null;
  const { label, tone } = CONFIDENCE_LABEL[value];
  return <Badge tone={tone}>{label}</Badge>;
}

const words = (value: string | null | undefined) => (value ? roleLabel(value) : null);

function JourneyCard({ journey, release, change, onOpenSystem }: {
  journey: Journey;
  release: KnowledgeRelease;
  change: CatalogueDiff["changes"][number]["change"] | undefined;
  onOpenSystem: (id: string) => void;
}) {
  const titleId = `journey-${journey.id}`;
  const names = new Map(release.systems.map((system) => [system.id, system.name]));
  const offering = (release.products ?? []).find((item) => item.id === journey.product_id);
  const order = offering?.order_types?.find((item) => item.code === journey.order_type_code);
  const parts = new Map((offering?.components ?? []).map((part) => [part.id, part.name]));
  const activities = [...(journey.activities ?? [])].sort((a, b) => byNumber(a.number, b.number));
  const titles = new Map(activities.map((item) => [item.number, `${item.number}. ${item.name}`]));
  const system = (id: string) => (
    <button key={id} type="button" className={SYSTEM_LINK} onClick={() => onOpenSystem(id)}>{names.get(id) ?? id}</button>
  );

  return (
    <article aria-labelledby={titleId} className="bg-surface border-line grid min-w-0 gap-6 rounded-md border border-solid p-6">
      <header className="grid gap-1">
        <h3 id={titleId} className="text-headline text-ink m-0 flex flex-wrap items-center gap-x-2 break-words">
          {journey.name}
          {change && <Badge tone={CHANGE_LABEL[change].tone}>{CHANGE_LABEL[change].label}</Badge>}
          <Confidence value={journey.confidence} />
        </h3>
        <p className="text-meta text-ink-muted m-0">
          {[offering?.name ?? journey.product_id, order?.name ?? journey.order_type_code].filter(Boolean).join(" › ")
            || "Not tied to a product offering"}
          {journey.source && ` · Source: ${journey.source}`}
        </p>
        {journey.description && <p className="text-body text-ink-soft m-0 mt-2 max-w-[68ch]">{journey.description}</p>}
      </header>

      <Table caption={`Activities of ${journey.name}, in order`} captionVisible>
        <TableHead>
          <tr>
            <TableHeaderCell>Activity</TableHeaderCell>
            <TableHeaderCell>Phase and track</TableHeaderCell>
            <TableHeaderCell>Performed by</TableHeaderCell>
            <TableHeaderCell>Supported by</TableHeaderCell>
            <TableHeaderCell>Mode</TableHeaderCell>
          </tr>
        </TableHead>
        <TableBody columns={5} empty={activities.length === 0 ? "No activities yet." : undefined}>
          {activities.map((item) => (
            <TableRow key={item.number}>
              <TableCell>
                <span className="grid gap-0.5">
                  <span className="text-body text-ink flex flex-wrap items-center gap-2">
                    {item.number}. {item.name}
                    {item.customer_visible && <Badge tone="neutral">Customer sees it</Badge>}
                    <Confidence value={item.confidence} />
                  </span>
                  {(item.system_function || item.description) && (
                    <span className="text-meta text-ink-muted">{item.system_function ?? item.description}</span>
                  )}
                  {(item.input || item.output) && (
                    <span className="text-meta text-ink-muted">{item.input ?? "…"} → {item.output ?? "…"}</span>
                  )}
                  {(item.component_ids ?? []).length > 0 && (
                    <span className="text-meta text-ink-muted">
                      Components: {item.component_ids?.map((id) => parts.get(id) ?? id).join(", ")}
                    </span>
                  )}
                </span>
              </TableCell>
              <TableCell>{[words(item.phase), item.track && item.track.toUpperCase() !== "MAIN" ? `${words(item.track)} track` : null]
                .filter(Boolean).join(" · ") || "Main"}</TableCell>
              <TableCell>{item.performing_system_id ? system(item.performing_system_id) : "Not stated"}</TableCell>
              <TableCell>
                {(item.supporting_system_ids ?? []).length === 0 ? "None" : (
                  <span className="flex flex-wrap gap-x-2">{item.supporting_system_ids?.map(system)}</span>
                )}
              </TableCell>
              <TableCell>{words(item.mode) ?? "Not stated"}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <div className="grid gap-2">
        <h4 className="text-body text-ink m-0 font-semibold">Flow</h4>
        <JourneyFlow journey={journey} names={names} />
      </div>

      {(journey.flow_rules ?? []).length > 0 && (
        <div className="grid gap-2">
          <h4 className="text-body text-ink m-0 font-semibold">Exceptions and side tracks ({journey.flow_rules?.length})</h4>
          <ul role="list" className="m-0 grid list-none gap-2 p-0">
            {journey.flow_rules?.map((rule) => (
              <li key={`${rule.kind}-${rule.from_activity}-${rule.to_activity}`} className="text-body text-ink-soft flex flex-wrap items-center gap-2">
                <Badge tone="neutral">{RULE_LABEL[rule.kind]}</Badge>
                <span>
                  From {titles.get(rule.from_activity) ?? rule.from_activity} to {titles.get(rule.to_activity) ?? rule.to_activity}
                  {rule.condition && ` when ${rule.condition}`}
                  {rule.kind === "parallel" && rule.rejoin_at && `, rejoining at ${titles.get(rule.rejoin_at) ?? rule.rejoin_at}`}
                </span>
                <Confidence value={rule.confidence} />
              </li>
            ))}
          </ul>
        </div>
      )}

      {(journey.integrations ?? []).length > 0 && (
        <Table caption={`How the activities of ${journey.name} hand over`} captionVisible>
          <TableHead>
            <tr>
              <TableHeaderCell>From → to</TableHeaderCell>
              <TableHeaderCell>Interaction</TableHeaderCell>
              <TableHeaderCell>Interface</TableHeaderCell>
              <TableHeaderCell>Payload</TableHeaderCell>
              <TableHeaderCell>Timing</TableHeaderCell>
            </tr>
          </TableHead>
          <TableBody columns={5}>
            {journey.integrations?.map((link) => (
              <TableRow key={`${link.from_activity}-${link.to_activity}`}>
                <TableCell>{titles.get(link.from_activity) ?? link.from_activity} → {titles.get(link.to_activity) ?? link.to_activity}</TableCell>
                <TableCell>{words(link.interaction) ?? "Not stated"}</TableCell>
                <TableCell>{link.interface ?? "Not stated"}</TableCell>
                <TableCell>{link.payload ?? "Not stated"}</TableCell>
                <TableCell>{words(link.timing) ?? "Not stated"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </article>
  );
}

/**
 * The version's journeys (ADR-0096): each one's activities in order with the
 * systems that perform them, the flow drawn from them, its exceptions and side
 * tracks, and how each activity hands over to the next. A system opens its dossier.
 */
export function JourneysView({ release, diff, onOpenSystem }: {
  release: KnowledgeRelease;
  diff?: CatalogueDiff;
  onOpenSystem: (id: string) => void;
}) {
  const journeys = release.journeys ?? [];
  const changed = new Map((diff?.changes ?? [])
    .filter((change) => change.item === "journey" && change.change !== "removed")
    .map((change) => [change.key, change.change]));
  if (journeys.length === 0) {
    return (
      <section aria-labelledby="journeys-title" className="bg-surface border-line grid gap-2 rounded-md border border-solid p-6">
        <h2 id="journeys-title" className="text-headline text-ink m-0">Journeys</h2>
        <p className="text-body text-ink-muted m-0 max-w-[68ch]">
          This version has no journeys yet. A maintainer adds them under Add content, Edit manually, or from a
          catalogue file.
        </p>
      </section>
    );
  }
  return (
    <section aria-labelledby="journeys-title" className="grid gap-4">
      <header className="grid gap-1">
        <h2 id="journeys-title" className="text-headline text-ink m-0">Journeys ({journeys.length})</h2>
        <p className="text-meta text-ink-muted m-0">The activities that fulfil each order, and the systems that perform them.</p>
      </header>
      {[...journeys].sort((a, b) => a.name.localeCompare(b.name)).map((journey) => (
        <JourneyCard key={journey.id} journey={journey} release={release} change={changed.get(journey.id)}
          onOpenSystem={onOpenSystem} />
      ))}
    </section>
  );
}
