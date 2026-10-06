import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import { useSearchParams } from "react-router-dom";

import { errorMessage } from "../api/errors";
import { KNOWLEDGE_PORTAL_URL, knowledgeApi, type PassageCitation } from "../api/knowledge";
import { useIsKnowledgeAdmin } from "../auth/useIsKnowledgeAdmin";
import { PageHeader } from "../components/shell";
import { AsyncState, ErrorNotice, asyncStatus } from "../components/states";
import { ButtonLink, Card } from "../components/ui";
import { useDocumentTitle } from "./useDocumentTitle";
import { ReviewOverdue } from "../components/ReviewOverdue";

/**
 * The exact published passage a Requirement cites, read-only (ADR-0099).
 *
 * The shared library is curated in the knowledge portal; anyone working on a
 * Requirement can still open what it cites. The link names the publication,
 * version, revision and passage, and the passage shows only while that exact
 * publication is live — a withdrawn or replaced one says so instead.
 */
export function ReferencePassagePage() {
  useDocumentTitle("Cited passage");
  const [params] = useSearchParams();
  const admin = useIsKnowledgeAdmin();
  const citation = citationFrom(params);
  const passage = useQuery({
    queryKey: ["reference-passage", citation],
    queryFn: () => knowledgeApi.passage(citation!),
    enabled: citation !== null,
    retry: false,
  });
  return (
    <>
      <PageHeader
        eyebrow="Shared library"
        title={passage.data?.title ?? "Cited passage"}
        description="The approved passage a requirement cites, exactly as it was published."
        actions={admin
          ? <ButtonLink variant="ghost" to={KNOWLEDGE_PORTAL_URL} reloadDocument
              icon={<ExternalLink size={16} aria-hidden="true" />}>Knowledge portal</ButtonLink>
          : undefined}
      />
      {citation === null
        ? <ErrorNotice message="This link does not name a complete citation. Open it again from the requirement that cites it." />
        : (
          <AsyncState
            status={asyncStatus(passage)}
            loading={{ label: "Loading the cited passage", variant: "panel" }}
            error={{ title: "We couldn’t show this passage", message: errorMessage(passage.error) }}
            onRetry={() => void passage.refetch()}
            headingLevel="h2"
          >
            {passage.data && (
              <Card as="section" padding="fluid" className="grid max-w-[var(--measure-document)] gap-3"
                aria-label="Cited published passage">
                <p className="text-meta text-ink-muted m-0">
                  Published version {passage.data.version_number}
                  {passage.data.section_path.length > 0 && <> · <bdi>{passage.data.section_path.join(" / ")}</bdi></>}
                  {" · "}<bdi>{passage.data.label}</bdi>
                </p>
                <ReviewOverdue dueOn={passage.data.review_due_on} subject="document" />
                <blockquote dir="auto" className="border-line m-0 border-0 border-l-2 border-solid pl-4">
                  <p className="text-document font-document text-ink m-0 whitespace-pre-line">{passage.data.text}</p>
                </blockquote>
                <p className="text-meta text-ink-muted m-0">
                  This is the approved passage, not a later working draft. Whether it applies is still
                  the requirement owner’s decision.
                </p>
              </Card>
            )}
          </AsyncState>
        )}
    </>
  );
}

/** The citation a link names, or nothing when any part is missing. */
function citationFrom(params: URLSearchParams): PassageCitation | null {
  const citation = {
    document_id: params.get("document") ?? "",
    publication_id: params.get("publication") ?? "",
    version_id: params.get("version") ?? "",
    revision_id: params.get("revision") ?? "",
    block_id: params.get("passage") ?? "",
  };
  return Object.values(citation).every(Boolean) ? citation : null;
}
