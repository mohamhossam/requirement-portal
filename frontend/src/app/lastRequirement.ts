/**
 * The requirement this person last opened, kept in this browser so the dashboard
 * can offer to resume it.
 *
 * Every access is guarded: Safari's private mode and a full or blocked storage
 * throw rather than returning null, and a resume link is never worth an error
 * screen, or a failed save after the requirement itself was saved.
 */
const KEY = "lastRequirementId";

export function rememberLastRequirement(id: string): void {
  try {
    localStorage.setItem(KEY, id);
  } catch {
    // Forgetting where you were is better than failing what you just did.
  }
}

export function lastRequirementId(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}
