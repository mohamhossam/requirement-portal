import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../api/client";
import { errorMessage } from "../../api/errors";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Skeleton } from "../../components/Skeleton";
import { Button } from "../../components/ui/Button";

export function OriginalPreview({ documentId, versionId, blockId }: {
  documentId: string; versionId: string; blockId: string;
}) {
  const [open, setOpen] = useState(false);
  const preview = useQuery({
    queryKey: ["private-original-preview", documentId, versionId, blockId],
    queryFn: () => api.previewLibraryOriginal(documentId, versionId, blockId),
    enabled: open,
    gcTime: 0,
    retry: false,
  });
  return <div className="original-source-preview">
    <Button variant="text" aria-expanded={open} onClick={() => setOpen(value => !value)}>
      {open ? "Hide original source" : "Compare with original source"}
    </Button>
    {open ? <>
      {preview.isPending ? <Skeleton label="Preparing safe source preview" bars={3} /> : null}
      {preview.isError ? <><ErrorNotice message={errorMessage(preview.error)} /><Button variant="text" onClick={() => void preview.refetch()}>Retry source preview</Button></> : null}
      {preview.data ? <figure>
        {preview.data.image_data ? <img src={preview.data.image_data} alt={`Original source: ${preview.data.location}`} /> : null}
        <figcaption>{preview.data.explanation}</figcaption>
      </figure> : null}
    </> : null}
  </div>;
}
