import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { useParams } from "react-router-dom";

import { errorMessage } from "../api/errors";
import { knowledgeRequest, type Evidence } from "../api/knowledge";
import { PageHeader } from "../components/shell";
import { AsyncState, asyncStatus } from "../components/states";
import { ButtonLink, Card } from "../components/ui";
import { useDocumentTitle } from "./useDocumentTitle";

export function ArchitectureEvidencePage() {
  useDocumentTitle("Architecture evidence");
  const { releaseId = "", chunkId = "" } = useParams();
  const evidence = useQuery({ queryKey: ["knowledge", releaseId, chunkId],
    queryFn: () => knowledgeRequest<Evidence>(
      `/architecture-knowledge/releases/${encodeURIComponent(releaseId)}/evidence/${encodeURIComponent(chunkId)}`,
    ), enabled: Boolean(releaseId && chunkId) });
  return (
    <>
      <PageHeader
        eyebrow="Architecture catalogue"
        title="Mapping evidence"
        description="The catalogue passage an architecture mapping cited."
        actions={<ButtonLink variant="ghost" to="/architecture-knowledge" icon={<ArrowLeft size={16} aria-hidden="true" />}>
          Architecture catalogue
        </ButtonLink>}
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
            <blockquote dir="auto" className="border-line m-0 border-0 border-l-2 border-solid pl-4">
              <p className="text-document font-document text-ink m-0 whitespace-pre-line">{evidence.data.text}</p>
            </blockquote>
          </Card>
        )}
      </AsyncState>
    </>
  );
}
