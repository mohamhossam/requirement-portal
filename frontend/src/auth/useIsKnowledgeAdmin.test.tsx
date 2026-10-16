import { renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import type { Actor } from "../api/client";
import { AuthContext, type AuthState } from "./authContext";
import { useIsKnowledgeAdmin } from "./useIsKnowledgeAdmin";

// KNOWLEDGE_ADMIN_ROLE defaults to "knowledge_admin" in tests (no runtime meta
// tag and no VITE_KNOWLEDGE_PORTAL_ROLE), which is the configuration under test.
function wrapperFor(actor: Actor | null) {
  const value = { actor } as AuthState;
  return ({ children }: { children: ReactNode }) => (
    <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
  );
}

describe("useIsKnowledgeAdmin", () => {
  it("is false with nobody signed in", () => {
    const { result } = renderHook(() => useIsKnowledgeAdmin(), { wrapper: wrapperFor(null) });
    expect(result.current).toBe(false);
  });

  it("is false for a signed-in person without the role", () => {
    const { result } = renderHook(() => useIsKnowledgeAdmin(), {
      wrapper: wrapperFor({ id: "a", display_name: "A", email: null, roles: ["member"] }),
    });
    expect(result.current).toBe(false);
  });

  it("is true for a holder of the configured role", () => {
    const { result } = renderHook(() => useIsKnowledgeAdmin(), {
      wrapper: wrapperFor({ id: "a", display_name: "A", email: null, roles: ["knowledge_admin"] }),
    });
    expect(result.current).toBe(true);
  });

  it("is false when the actor carries no roles at all", () => {
    const { result } = renderHook(() => useIsKnowledgeAdmin(), {
      wrapper: wrapperFor({ id: "a", display_name: "A", email: null }),
    });
    expect(result.current).toBe(false);
  });
});
