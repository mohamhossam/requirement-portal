const blockedReturnPaths = new Set(["/login", "/auth/callback", "/auth/silent-callback"]);

export function safeAuthReturnPath(candidate: string | null | undefined): string {
  if (!candidate) return "/";
  try {
    const resolved = new URL(candidate, window.location.origin);
    if (resolved.origin !== window.location.origin || blockedReturnPaths.has(resolved.pathname)) {
      return "/";
    }
    return `${resolved.pathname}${resolved.search}${resolved.hash}`;
  } catch {
    return "/";
  }
}
