import { ExternalLink, History, Sparkles } from "lucide-react";
import { useId } from "react";

import type { PriorArt, PriorArtMatch, PriorArtPassage } from "../../api/client";
import { ProvenanceDetails } from "../../components/ProvenanceDetails";
import { Badge, Card } from "../../components/ui";
import {
  NO_MATCHES,
  PASSAGE_SOURCE,
  PRIOR_ART_DESCRIPTION,
  PRIOR_ART_HEADING,
  REFERENCE_ONLY,
  WORK_ITEM_TYPE,
  priorArtShown,
} from "./labels";

const QUOTE = "font-serif text-document text-ink m-0 max-w-[var(--measure-document)] whitespace-pre-line";
const EXTERNAL =
  "text-accent inline-flex min-h-6 shrink-0 items-center gap-1 whitespace-nowrap underline underline-offset-2 focus-visible:outline-none";

/**
 * The work item's address, only when it is an `https:` link.
 *
 * It comes from a historic import, not from this app, so `javascript:` or
 * `data:` must never become a clickable href; plain `http:` is refused too, for a
 * page opened from a signed-in session.
 */
function httpsOnly(url: string | null): string | null {
  if (!url) return null;
  try {
    return new URL(url).protocol === "https:" ? url : null;
  } catch {
    return null;
  }
}

/** Epic › Feature › User Story, each id opening its work item in Azure DevOps. */
function Lineage({ passage }: { passage: PriorArtPassage }) {
  return (
    <ol className="text-meta text-ink-muted m-0 flex list-none flex-wrap items-center gap-x-1 p-0">
      {passage.lineage.map((item, index) => {
        const href = httpsOnly(item.url);
        return (
        <li className="inline-flex min-w-0 items-center gap-1" key={item.id}>
          {index > 0 && <span aria-hidden="true">›</span>}
          <span className="shrink-0 whitespace-nowrap">{WORK_ITEM_TYPE[item.type]}</span>
          {href ? (
            <a className={EXTERNAL} href={href} rel="noopener noreferrer" target="_blank">
              #{item.id}{" "}
              <ExternalLink aria-hidden="true" className="size-3.5" />
              <span className="sr-only">(opens Azure DevOps)</span>
            </a>
          ) : (
            <span>#{item.id}</span>
          )}
          <span className="text-ink-soft [overflow-wrap:anywhere]">{item.title}</span>
        </li>
        );
      })}
    </ol>
  );
}

function Passage({ passage }: { passage: PriorArtPassage }) {
  return (
    <li className="bg-surface-sunken grid gap-2 rounded-sm px-4 py-3">
      {passage.source_kind === "historic_brd" ? (
        <p className="text-meta text-ink-muted m-0 [overflow-wrap:anywhere]">
          <span className="text-ink font-semibold">{PASSAGE_SOURCE.historic_brd}</span>
          {passage.brd_filename ? ` · ${passage.brd_filename}` : ""}
          {passage.label ? ` · ${passage.label}` : ""}
        </p>
      ) : (
        <div className="grid gap-1">
          <p className="text-meta text-ink m-0 font-semibold">{PASSAGE_SOURCE.historic_backlog}</p>
          <Lineage passage={passage} />
        </div>
      )}
      <blockquote className={QUOTE}>{passage.excerpt}</blockquote>
    </li>
  );
}

function MatchCard({ match }: { match: PriorArtMatch }) {
  const headingId = useId();
  return (
    <Card as="article" aria-labelledby={headingId} className="grid min-w-0 gap-4" padding="fluid">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <h3 className="text-title text-ink m-0 min-w-0 [overflow-wrap:anywhere]" id={headingId}>
          {match.title}
        </h3>
        <Badge icon={<History aria-hidden="true" className="size-3.5" />}>Historic</Badge>
      </header>
      <div className="grid gap-1">
        <p className="text-meta text-ink-muted m-0 inline-flex items-center gap-1">
          <Sparkles aria-hidden="true" className="size-3.5" />
          Generated
        </p>
        <p className="text-body text-ink-soft m-0 max-w-[var(--measure-interface)]">{match.rationale}</p>
      </div>
      <section aria-labelledby={`${headingId}-evidence`} className="grid gap-3">
        <h4 className="text-label text-ink m-0" id={`${headingId}-evidence`}>
          What it was delivered as
        </h4>
        <ul className="m-0 grid list-none gap-3 p-0">
          {match.passages.map((passage, index) => (
            <Passage key={`${index}-${passage.excerpt.slice(0, 24)}`} passage={passage} />
          ))}
        </ul>
      </section>
    </Card>
  );
}

/**
 * Delivered work from old BRDs that resembles this requirement (Knowledge Center E2).
 *
 * Reference only: it sits beside the knowledge review, never inside it, and nothing here
 * can hold confirmation up.
 */
export function PriorArtPanel({ priorArt }: { priorArt: PriorArt }) {
  if (!priorArtShown(priorArt.status)) return null;
  const busy = priorArt.status === "checking" || priorArt.status === "waiting";
  const matches = priorArt.matches ?? [];
  return (
    <section className="grid min-w-0 gap-4" aria-labelledby="prior-art-title">
      <header className="grid gap-1">
        <h2 className="text-headline text-ink m-0" id="prior-art-title">{PRIOR_ART_HEADING}</h2>
        <p className="text-body text-ink-soft m-0 max-w-[var(--measure-interface)]" role={busy ? "status" : undefined}>
          {PRIOR_ART_DESCRIPTION[priorArt.status]} {REFERENCE_ONLY}
        </p>
      </header>
      {priorArt.status === "current" && matches.length === 0 && (
        <p className="text-body text-ink-muted m-0 rounded-md border border-dashed border-[var(--line)] px-4 py-3">
          {NO_MATCHES}
        </p>
      )}
      {matches.length > 0 && (
        <ul aria-label="Similar past requirements" className="m-0 grid list-none gap-4 p-0">
          {matches.map((match) => (
            <li key={match.historic_requirement_id}>
              <MatchCard match={match} />
            </li>
          ))}
        </ul>
      )}
      {priorArt.provenance && (
        <ProvenanceDetails label="How similar past requirements were found" provenance={priorArt.provenance} />
      )}
    </section>
  );
}
