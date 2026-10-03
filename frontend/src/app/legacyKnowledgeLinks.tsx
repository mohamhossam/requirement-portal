import { Navigate, useLocation, useParams } from "react-router-dom";

import { evidenceHref } from "../api/knowledge";

/**
 * Links saved before the library and catalogues moved to the knowledge portal
 * (ADR-0099). Citations and evidence still open, read-only, in this app;
 * anything else under the old addresses lands on Documents.
 */

/** A citation link from before the move: the same citation, in the read-only passage view. */
export function LegacyLibraryLink() {
  const { libraryId = "" } = useParams();
  const { search } = useLocation();
  const params = new URLSearchParams(search);
  if (!params.get("publication")) return <Navigate to="/documents" replace />;
  params.set("document", libraryId);
  return <Navigate to={`/references/passage?${params}`} replace />;
}

/** An evidence link from before the move, in the read-only evidence view. */
export function LegacyEvidenceLink() {
  const { releaseId = "", chunkId = "" } = useParams();
  return <Navigate to={evidenceHref(releaseId, chunkId)} replace />;
}
