import { KNOWLEDGE_ADMIN_ROLE } from "../api/knowledge";
import { useAuth } from "./authContext";

/**
 * Whether the signed-in person can open the knowledge portal (ADR-0099).
 *
 * Only knowledge admins curate the library and the catalogues there; everyone
 * else reads what they publish through this app's read-only views.
 */
export function useIsKnowledgeAdmin(): boolean {
  return Boolean(useAuth()?.actor?.roles?.includes(KNOWLEDGE_ADMIN_ROLE));
}
