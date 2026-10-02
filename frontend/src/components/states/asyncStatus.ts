/**
 * Which of the four states a surface is in.
 *
 * Its own file because it is not a component: co-located with `AsyncState` it
 * broke Fast Refresh for the whole module, so an edit to the loading block
 * reloaded the page instead of the component.
 */
export type AsyncStatus = "pending" | "error" | "empty" | "ready";

/**
 * The adapter from a TanStack query to that status. Deliberately typed to the two
 * flags it reads rather than to `UseQueryResult`, so an infinite query, a
 * composed pair of queries or a hand-rolled object all fit.
 */
export function asyncStatus(
  query: { isPending: boolean; isError: boolean },
  isEmpty?: boolean,
): AsyncStatus {
  if (query.isPending) return "pending";
  if (query.isError) return "error";
  return isEmpty ? "empty" : "ready";
}
