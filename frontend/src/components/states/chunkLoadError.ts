/**
 * A lazy route's file that no longer exists: the app was redeployed while this
 * tab was open, so its fingerprinted chunk names point at the old release.
 */
export function isChunkLoadError(error: unknown): boolean {
  return error instanceof Error && (
    error.name === "ChunkLoadError"
    || /dynamically imported module|Importing a module script failed/i.test(error.message)
  );
}
