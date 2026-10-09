import { KNOWLEDGE_ADMIN_ROLE } from "../api/knowledge";
import { useAuth } from "./authContext";

/**
 * Whether the signed-in person sees the links to the knowledge portal (ADR-0099, ADR-0104).
 *
 * Only knowledge admins curate the library and the catalogues there; everyone
 * else reads what they publish through this app's read-only views. With no role
 * configured, everyone signed in sees the links and the portal decides.
 */
export function useIsKnowledgeAdmin(): boolean {
  const actor = useAuth()?.actor;
  if (!actor) return false;
  return (
    KNOWLEDGE_ADMIN_ROLE === null ||
    Boolean(actor.roles?.includes(KNOWLEDGE_ADMIN_ROLE))
  );
}
