import { createContext, useContext } from "react";

import type { Actor, IdentityConfig } from "../api/client";

export type AuthState = {
  actor: Actor | null;
  config: IdentityConfig | null;
  loading: boolean;
  reconciling: boolean;
  error: string | null;
  sessionExpired: boolean;
  signingInChoice: string | null;
  signIn: (choiceId?: string) => Promise<void>;
  signOut: () => Promise<void>;
  switchFakeActor: (actorId: string) => Promise<void>;
};

export const AuthContext = createContext<AuthState | null>(null);

export function useAuth() {
  return useContext(AuthContext);
}
