import { useQuery } from "@tanstack/react-query";
import { useId, type ReactNode } from "react";

import { errorMessage } from "../../api/errors";
import { knowledgeApi } from "../../api/knowledge";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Skeleton } from "../../components/Skeleton";
import { Button, Modal, ModalBody, ModalFooter, ModalHeader } from "../../components/ui";
import { catalogueKeys } from "./keys";

/** The quote marked inside its passage when it appears there word for word. */
function highlighted(text: string, quote: string): ReactNode {
  const at = quote ? text.indexOf(quote) : -1;
  if (at < 0) return text;
  return <>{text.slice(0, at)}<mark>{quote}</mark>{text.slice(at + quote.length)}</>;
}

/**
 * A suggestion's citation read in place: the cited passage, highlighted, with
 * the passages before and after it, re-read from the stored document.
 */
export function PassageDialog({ releaseId, versionId, documentTitle, location, quote, onClose }: {
  releaseId: string;
  versionId: string;
  documentTitle: string;
  location: string;
  quote: string;
  onClose: () => void;
}) {
  const titleId = useId();
  const passage = useQuery({
    queryKey: catalogueKeys.passage(releaseId, versionId, location),
    queryFn: () => knowledgeApi.passage(releaseId, versionId, location),
  });
  const neighbour = (item: { location: string; text: string }) => (
    <div key={item.location} className="grid gap-0.5">
      <span className="text-meta text-ink-muted">{item.location}</span>
      <p className="text-document font-document text-ink-muted m-0 whitespace-pre-line" dir="auto">{item.text}</p>
    </div>
  );
  return (
    <Modal variant="dialog" labelledBy={titleId} onClose={onClose}>
      <ModalHeader id={titleId} title={documentTitle} description={`Cited at ${location}`} />
      <ModalBody>
        {passage.isPending && <Skeleton label="Reading the document" bars={4} />}
        {passage.error && <ErrorNotice message={errorMessage(passage.error)} />}
        {passage.data && (
          <div className="grid max-h-[60vh] gap-4 overflow-y-auto">
            {passage.data.before.map(neighbour)}
            <div className="border-accent bg-accent-wash grid gap-0.5 rounded-sm border-0 border-l-[3px] border-solid px-3 py-2">
              <span className="text-meta text-ink-soft">{passage.data.passage.location} · cited passage</span>
              <p className="text-document font-document text-ink m-0 whitespace-pre-line" dir="auto">
                {highlighted(passage.data.passage.text, quote)}
              </p>
            </div>
            {passage.data.after.map(neighbour)}
          </div>
        )}
      </ModalBody>
      <ModalFooter>
        <Button onClick={onClose}>Close</Button>
      </ModalFooter>
    </Modal>
  );
}
