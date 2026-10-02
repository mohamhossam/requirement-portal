import type { CatalogueChange, CatalogueDiff } from "../../api/knowledge";
import { Badge } from "../../components/ui";
import { CHANGE_LABEL, FIELD_LABEL, ITEM_LABEL, changeStory, systemOf } from "./labels";

const ORDER = [
  "system", "component", "capability", "domain", "landscape_domain", "product", "journey", "relationship", "document",
] as const;

/** One change. Under a system that caused it, the parent badge already says how, so it is not repeated. */
function Row({ change, follow = false }: { change: CatalogueChange; follow?: boolean }) {
  return (
    <span className={follow ? "grid" : "grid grid-cols-[auto_minmax(0,1fr)] items-baseline gap-x-2"}>
      {!follow && <Badge tone={CHANGE_LABEL[change.change].tone}>{CHANGE_LABEL[change.change].label}</Badge>}
      <span className="text-body text-ink break-words" dir="auto">
        {change.label}
        {change.fields.length > 0 && (
          <span className="text-meta text-ink-muted">
            {" "}({change.fields.map((field) => FIELD_LABEL[field] ?? field).join(", ")})
          </span>
        )}
      </span>
    </span>
  );
}

/**
 * Added, changed and removed items, grouped by what they are. Words, not colour
 * alone. A system added or removed outright carries its own components, capabilities and
 * dependencies beneath it, so one decision reads as one change and not as eight.
 */
export function DiffList({ diff, empty, headingLevel = "h3" }: {
  diff: CatalogueDiff;
  empty: string;
  headingLevel?: "h3" | "h4" | "h5";
}) {
  if (diff.changes.length === 0) return <p className="text-body text-ink-muted m-0">{empty}</p>;
  const Heading = headingLevel;
  const causes = new Map(diff.changes
    .filter((change) => change.item === "system" && change.change !== "changed")
    .map((change) => [change.key, change.change]));
  const followsFrom = (change: CatalogueChange) => {
    if (change.item === "system" || change.item === "document") return null;
    const owners = systemOf(change);
    return owners.find((id) => causes.get(id) === change.change) ?? null;
  };
  const nested = new Map<string, CatalogueChange[]>();
  const own: CatalogueChange[] = [];
  for (const change of diff.changes) {
    const cause = followsFrom(change);
    if (cause) nested.set(cause, [...(nested.get(cause) ?? []), change]);
    else own.push(change);
  }

  return (
    <div className="grid gap-4">
      <p className="text-body text-ink-soft m-0">{changeStory(diff)}</p>
      {ORDER.map((item) => {
        const group = own.filter((change) => change.item === item);
        if (group.length === 0) return null;
        return (
          <section key={item} className="grid gap-2" aria-label={`${ITEM_LABEL[item]} changes`}>
            <Heading className="text-label text-ink-muted m-0">{ITEM_LABEL[item]} ({group.length})</Heading>
            <ul className="border-line m-0 grid list-none rounded-md border border-solid p-0 [&>li+li]:[border-top:1px_solid_var(--line)]">
              {group.map((change) => {
                const follows = change.item === "system" ? nested.get(change.key) ?? [] : [];
                return (
                  <li key={`${change.change}-${change.key}`} className="grid gap-2 px-3 py-2">
                    <Row change={change} />
                    {follows.length > 0 && (
                      <div className="grid gap-1 pl-4">
                        <p className="text-meta text-ink-muted m-0">
                          {change.change === "removed" ? "Removed with it" : "Added with it"} ({follows.length})
                        </p>
                        <ul className="text-ink-soft m-0 grid list-disc gap-1 pl-5">
                          {follows.map((follow) => (
                            <li key={`${follow.item}-${follow.change}-${follow.key}`}><Row change={follow} follow /></li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
