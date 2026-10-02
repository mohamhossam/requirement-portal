import type { CatalogueDiff, KnowledgeRelease, OfferingPoint, ProductOffering, SourceConfidence } from "../../api/knowledge";
import {
  Badge, Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow, cx,
} from "../../components/ui";
import { FOCUS_RING } from "../../components/ui/recipes";
import { CHANGE_LABEL, CONFIDENCE_LABEL, roleLabel } from "./labels";

const SYSTEM_LINK = cx(
  "text-body text-ink-soft hover:text-ink inline min-h-6 cursor-pointer border-0 bg-transparent p-0 text-left underline underline-offset-2",
  FOCUS_RING,
);

function Confidence({ value }: { value: SourceConfidence | null | undefined }) {
  if (!value) return null;
  const { label, tone } = CONFIDENCE_LABEL[value];
  return <Badge tone={tone}>{label}</Badge>;
}

const yesNo = (value: boolean | null | undefined) => (value == null ? "Not stated" : value ? "Yes" : "No");

function Points({ title, points }: { title: string; points: OfferingPoint[] }) {
  if (points.length === 0) return null;
  return (
    <div className="grid content-start gap-2">
      <h4 className="text-body text-ink m-0 font-semibold">{title}</h4>
      <ul role="list" className="m-0 grid list-none gap-2 p-0">
        {points.map((point) => (
          <li key={point.name} className="grid gap-0.5">
            <span className="text-body text-ink flex flex-wrap items-center gap-2">
              {point.name} <Confidence value={point.confidence} />
            </span>
            {point.description && <span className="text-meta text-ink-muted max-w-[68ch]">{point.description}</span>}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Offering({ offering, names, change, onOpenSystem }: {
  offering: ProductOffering;
  names: Map<string, string>;
  change: CatalogueDiff["changes"][number]["change"] | undefined;
  onOpenSystem: (id: string) => void;
}) {
  const titleId = `offering-${offering.id}`;
  const systems = [...new Set((offering.components ?? []).flatMap((part) =>
    (part.responsibilities ?? []).map((duty) => duty.system_id)))];
  const orderNames = new Map((offering.order_types ?? []).map((order) => [order.code, order.name]));
  const facts = [offering.family && `${offering.family} family`, offering.version && `version ${offering.version}`,
    offering.lifecycle && roleLabel(offering.lifecycle)].filter(Boolean).join(" · ");
  const system = (id: string) => (
    <button type="button" className={SYSTEM_LINK} onClick={() => onOpenSystem(id)}>{names.get(id) ?? id}</button>
  );

  return (
    <article aria-labelledby={titleId} className="bg-surface border-line grid min-w-0 gap-6 rounded-md border border-solid p-6">
      <header className="grid gap-1">
        <h3 id={titleId} className="text-headline text-ink m-0 flex flex-wrap items-center gap-x-2 break-words">
          {offering.name}
          {change && <Badge tone={CHANGE_LABEL[change].tone}>{CHANGE_LABEL[change].label}</Badge>}
          <Confidence value={offering.confidence} />
        </h3>
        <p className="text-meta text-ink-muted m-0 flex flex-wrap gap-x-2">
          {offering.code && <span className="font-mono">{offering.code}</span>}
          {facts && <span>{offering.code ? "· " : ""}{facts}</span>}
          {offering.source && <span>· Source: {offering.source}</span>}
        </p>
        {offering.proposition && <p className="text-body text-ink-soft m-0 mt-2 max-w-[68ch]">{offering.proposition}</p>}
      </header>

      {(offering.rules ?? []).length > 0 && (
        <div className="grid gap-2">
          <h4 className="text-body text-ink m-0 font-semibold">Rules</h4>
          <ul className="text-body text-ink-soft m-0 grid gap-1 pl-5">
            {offering.rules?.map((rule) => <li key={rule} className="max-w-[68ch]">{rule}</li>)}
          </ul>
        </div>
      )}

      <div className="grid gap-2">
        <h4 className="text-body text-ink m-0 font-semibold">Order types ({offering.order_types?.length ?? 0})</h4>
        {(offering.order_types ?? []).length === 0 ? (
          <p className="text-meta text-ink-muted m-0">No order types yet.</p>
        ) : (
          <ul role="list" className="m-0 grid list-none gap-2 p-0">
            {offering.order_types?.map((order) => (
              <li key={order.code} className="grid gap-0.5">
                <span className="text-body text-ink flex flex-wrap items-center gap-2">
                  {order.name} <span className="text-meta text-ink-muted font-mono">{order.code}</span>
                  {order.enabled === false && <Badge tone="neutral">Not offered yet</Badge>}
                  <Confidence value={order.confidence} />
                </span>
                {order.description && <span className="text-meta text-ink-muted max-w-[68ch]">{order.description}</span>}
              </li>
            ))}
          </ul>
        )}
      </div>

      <Table caption={`Components of ${offering.name}`} captionVisible>
        <TableHead>
          <tr>
            <TableHeaderCell>Component</TableHeaderCell>
            <TableHeaderCell>Type</TableHeaderCell>
            <TableHeaderCell>Mandatory</TableHeaderCell>
            <TableHeaderCell>Customer visible</TableHeaderCell>
            <TableHeaderCell>Confidence</TableHeaderCell>
          </tr>
        </TableHead>
        <TableBody columns={5} empty={(offering.components ?? []).length === 0 ? "No components yet." : undefined}>
          {offering.components?.map((part) => (
            <TableRow key={part.id}>
              <TableCell>
                <span className="grid gap-0.5">
                  <span className="text-body text-ink">{part.name}</span>
                  {part.code && <span className="text-meta text-ink-muted font-mono">{part.code}</span>}
                  {part.description && <span className="text-meta text-ink-muted">{part.description}</span>}
                </span>
              </TableCell>
              <TableCell>{part.kind ? roleLabel(part.kind) : "Not stated"}</TableCell>
              <TableCell>{yesNo(part.mandatory)}</TableCell>
              <TableCell>{yesNo(part.customer_visible)}</TableCell>
              <TableCell>{part.confidence ? <Confidence value={part.confidence} /> : "Not stated"}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      {systems.length > 0 && (
        <div className="grid gap-3">
          <Table caption={`Which system does what for ${offering.name}`} captionVisible>
            <TableHead>
              <tr>
                <TableHeaderCell>Component</TableHeaderCell>
                {systems.map((id) => <TableHeaderCell key={id}>{names.get(id) ?? id}</TableHeaderCell>)}
              </tr>
            </TableHead>
            <TableBody columns={systems.length + 1}>
              {offering.components?.map((part) => (
                <TableRow key={part.id}>
                  {/* A row header names the component each role is for. */}
                  <th scope="row" className="text-body text-ink px-3 py-2 text-left font-normal">{part.name}</th>
                  {systems.map((id) => {
                    const roles = (part.responsibilities ?? []).filter((duty) => duty.system_id === id);
                    return (
                      <TableCell key={id}>
                        {roles.length === 0
                          ? <span className="text-ink-faint" aria-label="None">—</span>
                          : roles.map((duty) => roleLabel(duty.role)).join(", ")}
                      </TableCell>
                    );
                  })}
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <div className="grid gap-2">
            <h4 className="text-body text-ink m-0 font-semibold">What each system does</h4>
            <ul role="list" className="m-0 grid list-none gap-3 p-0">
              {offering.components?.flatMap((part) => (part.responsibilities ?? []).map((duty) => (
                <li key={`${part.id}-${duty.system_id}-${duty.role}`} className="grid gap-0.5">
                  <span className="text-body text-ink flex flex-wrap items-center gap-x-2">
                    <span>{part.name} —</span> {system(duty.system_id)}
                    <span className="text-meta text-ink-muted">{roleLabel(duty.role)}</span>
                    <Confidence value={duty.confidence} />
                  </span>
                  <span className="text-meta text-ink-muted max-w-[68ch]">
                    {duty.description}
                    {(duty.order_types ?? []).length > 0 && ` For ${duty.order_types?.map((code) => orderNames.get(code) ?? code).join(", ")}.`}
                  </span>
                </li>
              )))}
            </ul>
          </div>
        </div>
      )}

      {((offering.values ?? []).length > 0 || (offering.audiences ?? []).length > 0) && (
        <div className="grid gap-6 lg:grid-cols-2">
          <Points title="Customer value" points={offering.values ?? []} />
          <Points title="Who it is for" points={offering.audiences ?? []} />
        </div>
      )}
    </article>
  );
}

/**
 * The version's product offerings (ADR-0095): what each is made of, how it is
 * ordered, and which systems deliver each component in which role. A system
 * opens its dossier. A version in progress marks the offerings it adds or changes.
 */
export function ProductsView({ release, diff, onOpenSystem }: {
  release: KnowledgeRelease;
  diff?: CatalogueDiff;
  onOpenSystem: (id: string) => void;
}) {
  const offerings = release.products ?? [];
  const names = new Map(release.systems.map((system) => [system.id, system.name]));
  const changed = new Map((diff?.changes ?? [])
    .filter((change) => change.item === "product" && change.change !== "removed")
    .map((change) => [change.key, change.change]));
  if (offerings.length === 0) {
    return (
      <section aria-labelledby="offerings-title" className="bg-surface border-line grid gap-2 rounded-md border border-solid p-6">
        <h2 id="offerings-title" className="text-headline text-ink m-0">Product offerings</h2>
        <p className="text-body text-ink-muted m-0 max-w-[68ch]">
          This version has no product offerings yet. A maintainer adds them under Add content, Edit manually, or
          from a catalogue file.
        </p>
      </section>
    );
  }
  return (
    <section aria-labelledby="offerings-title" className="grid gap-4">
      <header className="grid gap-1">
        <h2 id="offerings-title" className="text-headline text-ink m-0">Product offerings ({offerings.length})</h2>
        <p className="text-meta text-ink-muted m-0">What each offering is made of, and which systems deliver it.</p>
      </header>
      {[...offerings].sort((a, b) => a.name.localeCompare(b.name)).map((offering) => (
        <Offering key={offering.id} offering={offering} names={names} change={changed.get(offering.id)}
          onOpenSystem={onOpenSystem} />
      ))}
    </section>
  );
}
