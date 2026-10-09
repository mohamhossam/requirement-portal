import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import { useParams } from "react-router-dom";

import { errorMessage } from "../api/errors";
import { KNOWLEDGE_PORTAL_URL, knowledgeApi } from "../api/knowledge";
import { useIsKnowledgeAdmin } from "../auth/useIsKnowledgeAdmin";
import { PageHeader } from "../components/shell";
import { AsyncState, asyncStatus } from "../components/states";
import { ButtonLink, Card } from "../components/ui";
import { useDocumentTitle } from "./useDocumentTitle";
import { ReviewOverdue } from "../components/ReviewOverdue";

/**
 * The catalogue passage an architecture mapping cited, read-only (ADR-0099).
 *
 * The catalogue is curated in the knowledge portal; anyone reviewing a
 * Requirement's architecture impact can still read the evidence behind it,
 * from the published catalogue version the mapping used.
 */
export function ArchitectureEvidencePage() {
  useDocumentTitle("Architecture evidence");
  const { releaseId = "", chunkId = "" } = useParams();
  const admin = useIsKnowledgeAdmin();
  const evidence = useQuery({
    queryKey: ["architecture-evidence", releaseId, chunkId],
    queryFn: () => knowledgeApi.evidence(releaseId, chunkId),
    enabled: Boolean(releaseId && chunkId),
    retry: false,
  });
  return (
    <>
      <PageHeader
        eyebrow="Architecture catalogue"
        title="Mapping evidence"
        description="The catalogue passage an architecture mapping cited."
        actions={admin && KNOWLEDGE_PORTAL_URL !== null
          ? <ButtonLink variant="ghost" to={KNOWLEDGE_PORTAL_URL} reloadDocument
              icon={<ExternalLink size={16} aria-hidden="true" />}>Knowledge portal</ButtonLink>
          : undefined}
      />
      <AsyncState
        status={asyncStatus(evidence)}
        loading={{ label: "Loading the cited passage", variant: "panel" }}
        error={{ title: "We couldn’t load this evidence", message: errorMessage(evidence.error) }}
        onRetry={() => void evidence.refetch()}
        headingLevel="h2"
      >
        {evidence.data && (
          <Card as="section" padding="fluid" className="grid max-w-[var(--measure-document)] gap-3" aria-label="Cited passage">
            <p className="text-meta text-ink-muted m-0">
              {evidence.data.source_label} · {evidence.data.location} · version <span className="font-mono">{releaseId}</span>
            </p>
            <ReviewOverdue dueOn={evidence.data.system_review_due_on} subject="system" />
            <blockquote dir="auto" className="border-line m-0 border-0 border-l-2 border-solid pl-4">
              <p className="text-document font-document text-ink m-0 whitespace-pre-line">{evidence.data.text}</p>
            </blockquote>
          </Card>
        )}
      </AsyncState>
    </>
  );
}
