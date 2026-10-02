import type { Requirement } from "../../api/client";

/**
 * The structured parts of a requirement, beside its business need.
 *
 * Source used to show the business need and nothing else, in the drawer only:
 * the desired outcome, customer context, channels, systems, rules and
 * constraints a person typed at intake were not on the Source step at all.
 * Only what was filled in is listed — an empty "Constraints: —" row says
 * nothing a person can act on.
 */
const TEXT: Array<[keyof Requirement, string]> = [
  ["desired_outcome", "Desired outcome"],
  ["customer_context", "Customer context"],
];
const LISTS: Array<[keyof Requirement, string]> = [
  ["channels", "Channels"],
  ["systems", "Systems"],
  ["business_rules", "Business rules"],
  ["constraints", "Constraints"],
];

export function RequirementFacts({ requirement }: { requirement: Requirement }) {
  const text = TEXT.filter(([key]) => typeof requirement[key] === "string" && (requirement[key] as string).trim());
  const lists = LISTS.filter(([key]) => Array.isArray(requirement[key]) && (requirement[key] as string[]).length > 0);
  if (!text.length && !lists.length) return null;
  return (
    <dl className="m-0 grid gap-4">
      {text.map(([key, label]) => (
        <div className="grid gap-1" key={key}>
          <dt className="text-label text-ink-muted">{label}</dt>
          <dd className="font-serif text-document text-ink m-0 max-w-[var(--measure-document)] whitespace-pre-line">
            {requirement[key] as string}
          </dd>
        </div>
      ))}
      {lists.map(([key, label]) => (
        <div className="grid gap-1" key={key}>
          <dt className="text-label text-ink-muted">{label}</dt>
          <dd className="m-0">
            <ul className="font-serif text-document text-ink m-0 grid max-w-[var(--measure-document)] gap-1 pl-5">
              {(requirement[key] as string[]).map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}
            </ul>
          </dd>
        </div>
      ))}
    </dl>
  );
}
