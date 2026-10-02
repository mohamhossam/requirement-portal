import { useQuery } from "@tanstack/react-query";
import { Navigate, useParams } from "react-router-dom";

import { api } from "../api/client";
import { LoadingState } from "../components/states";
import { queryKeys } from "./queryKeys";
import { stagePath } from "./stagePath";

export function RequirementEntryRedirect() {
  const { id = "" } = useParams();
  const result = useQuery({
    queryKey: queryKeys.scope("requirement-entry", id),
    queryFn: () => api.listRequirements({ q: id, limit: 100 }),
    enabled: Boolean(id),
  });
  // No <main> of its own any more: the shell owns it, and this renders inside it.
  if (result.isPending) return <LoadingState label="Opening the current stage" variant="page" />;
  const item = result.data?.requirements.find((candidate) => candidate.id === id);
  return <Navigate replace to={item ? stagePath(item) : `/requirements/${id}/capture`} />;
}
