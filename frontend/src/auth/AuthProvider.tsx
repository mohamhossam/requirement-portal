import { useQueryClient } from "@tanstack/react-query";
import {
  type ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { UserManager, WebStorageStateStore, type User } from "oidc-client-ts";
import { Navigate, useLocation } from "react-router-dom";

import {
  api,
  configureAuthentication,
  configureAuthenticationHeaders,
  replaceAuthenticationHeaders,
  type Actor,
  type IdentityConfig,
} from "../api/client";
import { errorMessage } from "../api/errors";
import { configureQueryActor } from "../app/queryKeys";
import { AuthContext, type AuthState, useAuth } from "./authContext";
import { LoginPage } from "./LoginPage";
import { safeAuthReturnPath } from "./returnPath";
import { Skeleton } from "../components/Skeleton";
const fakeActorKey = "requirement-ai.fake-actor";
const returnPathKey = "requirement-ai.auth-return-path";

function oidcManager(config: IdentityConfig) {
  if (!config.authority || !config.client_id) throw new Error("OIDC configuration is incomplete.");
  return new UserManager({
    authority: config.authority,
    client_id: config.client_id,
    redirect_uri: `${window.location.origin}/auth/callback`,
    silent_redirect_uri: `${window.location.origin}/auth/silent-callback`,
    post_logout_redirect_uri: window.location.origin,
    response_type: "code",
    scope: config.scopes ?? "openid profile email",
    automaticSilentRenew: true,
    userStore: new WebStorageStateStore({ store: window.sessionStorage }),
  });
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [config, setConfig] = useState<IdentityConfig | null>(null);
  const [actor, setActor] = useState<Actor | null>(null);
  const [loading, setLoading] = useState(true);
  const [reconciling, setReconciling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionExpired, setSessionExpired] = useState(false);
  const [signingInChoice, setSigningInChoice] = useState<string | null>(null);
  const managerRef = useRef<UserManager | null>(null);
  const actorIdRef = useRef<string | null>(null);
  const started = useRef(false);
  const transition = useRef(0);
  const renewal = useRef<Promise<void> | null>(null);
  const signedOut = useRef(false);
  const signInStarted = useRef(false);

  const loadActor = useCallback(async () => {
    const sequence = ++transition.current;
    setReconciling(true);
    try {
    const current = await api.getCurrentActor();
    if (sequence !== transition.current) return;
    if (actorIdRef.current !== current.id) {
      await queryClient.cancelQueries();
      if (sequence !== transition.current) return;
      queryClient.clear();
      configureQueryActor(current.id);
      actorIdRef.current = current.id;
    }
    setActor(current);
    setError(null);
    setSessionExpired(false);
    } catch (reason) {
      if (sequence !== transition.current) return;
      if (sequence === transition.current) {
        queryClient.clear();
        configureQueryActor(null);
        actorIdRef.current = null;
        setActor(null);
        setSessionExpired(true);
        setError(errorMessage(reason));
      }
      throw reason;
    } finally {
      if (sequence === transition.current) setReconciling(false);
    }
  }, [queryClient]);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    let disposed = false;
    let removeUserLoaded: (() => void) | undefined;
    configureAuthentication(() => ({}));
    void api.getIdentityConfig().then(async (resolved) => {
      if (disposed) return;
      setConfig(resolved);
      if (resolved.mode === "fake") {
        const remembered = sessionStorage.getItem(fakeActorKey);
        const selected = resolved.fake_actors.some((item) => item.id === remembered)
          ? remembered
          : resolved.fake_actors[0]?.id;
        if (!selected) throw new Error("Fake identity mode has no configured personas.");
        sessionStorage.setItem(fakeActorKey, selected);
        configureAuthentication(() => ({ "X-Fake-Actor-Id": selected }));
        await loadActor();
        return;
      }

      const manager = oidcManager(resolved);
      managerRef.current = manager;
      let currentUser: User | null;
      if (window.location.pathname === "/auth/silent-callback") {
        await manager.signinSilentCallback();
        currentUser = await manager.getUser();
      } else if (window.location.pathname === "/auth/callback") {
        currentUser = await manager.signinRedirectCallback();
        const returnPath = safeAuthReturnPath(sessionStorage.getItem(returnPathKey));
        sessionStorage.removeItem(returnPathKey);
        window.history.replaceState({}, "", returnPath);
      } else {
        currentUser = await manager.getUser();
      }
      if (disposed) return;
      let subject = currentUser?.profile?.sub ?? null;
      configureAuthentication(
        () => currentUser?.access_token ? { Authorization: `Bearer ${currentUser.access_token}` } : {} as Record<string, string>,
        () => {
          setSessionExpired(true);
          if (renewal.current) return;
          renewal.current = manager.signinSilent().then(async (renewed) => {
            if (!renewed) throw new Error("OIDC silent renewal returned no user.");
          }).catch(() => setSessionExpired(true)).finally(() => { renewal.current = null; });
        },
      );
      const onUserLoaded = (renewed: User) => {
        if (disposed || signedOut.current) return;
        const headers = () => ({ Authorization: `Bearer ${renewed.access_token}` });
        if (subject !== null && renewed.profile?.sub === subject && actorIdRef.current !== null) {
          // A renewed token for the same person: keep what is in flight and on
          // screen, and refetch what failed while the old token had expired.
          replaceAuthenticationHeaders(headers);
          setSessionExpired(false);
          void queryClient.invalidateQueries();
          return;
        }
        subject = renewed.profile?.sub ?? null;
        configureAuthenticationHeaders(headers);
        void loadActor().catch(() => setSessionExpired(true));
      };
      manager.events.addUserLoaded(onUserLoaded);
      removeUserLoaded = () => manager.events.removeUserLoaded(onUserLoaded);
      if (currentUser && !currentUser.expired) await loadActor();
    }).catch((reason: unknown) => { if (!disposed) setError(errorMessage(reason)); })
      .finally(() => { if (!disposed) setLoading(false); });
    return () => {
      disposed = true;
      started.current = false;
      transition.current += 1;
      removeUserLoaded?.();
    };
  }, [loadActor, queryClient]);

  const value = useMemo<AuthState>(() => ({
    actor,
    config,
    loading,
    reconciling,
    error,
    sessionExpired,
    signingInChoice,
    signIn: async (choiceId?: string) => {
      if (signInStarted.current) return;
      signedOut.current = false;
      const manager = managerRef.current;
      if (!manager || !config) {
        setError("Sign-in is not configured. Reload the page or contact your administrator.");
        return;
      }
      const choice = choiceId
        ? config.login_choices.find((item) => item.id === choiceId)
        : undefined;
      if (choiceId && !choice) {
        setError("That sign-in method is not available.");
        return;
      }
      const requested = window.location.pathname === "/login"
        ? new URLSearchParams(window.location.search).get("returnTo")
        : `${window.location.pathname}${window.location.search}${window.location.hash}`;
      sessionStorage.setItem(returnPathKey, safeAuthReturnPath(requested));
      signInStarted.current = true;
      setSigningInChoice(choiceId ?? "default");
      setError(null);
      try {
        await manager.signinRedirect({
          extraQueryParams: choice?.authorization_parameters,
        });
      } catch (reason) {
        setError(errorMessage(reason));
      } finally {
        signInStarted.current = false;
        setSigningInChoice(null);
      }
    },
    signOut: async () => {
      signedOut.current = true;
      transition.current += 1;
      setReconciling(true);
      configureAuthenticationHeaders(() => ({}));
      await queryClient.cancelQueries();
      queryClient.clear();
      configureQueryActor(null);
      actorIdRef.current = null;
      setActor(null);
      setReconciling(false);
      if (config?.mode === "oidc" && managerRef.current) await managerRef.current.signoutRedirect();
    },
    switchFakeActor: async (actorId: string) => {
      signedOut.current = false;
      transition.current += 1;
      setReconciling(true);
      configureAuthenticationHeaders(() => ({ "X-Fake-Actor-Id": actorId }));
      sessionStorage.setItem(fakeActorKey, actorId);
      await queryClient.cancelQueries();
      queryClient.clear();
      configureQueryActor(null);
      actorIdRef.current = null;
      await loadActor();
    },
  }), [actor, config, error, loadActor, loading, queryClient, reconciling, sessionExpired, signingInChoice]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function AuthGate({ children }: { children: ReactNode }) {
  const auth = useAuth();
  const location = useLocation();
  // This one keeps its own <main>: the gate renders BEFORE the app shell, so
  // there is no landmark around it yet.
  if (!auth || auth.loading) {
    return (
      <main className="loading-screen grid min-h-dvh place-content-center justify-items-center p-10">
        <Skeleton label="Signing you in" variant="page" />
      </main>
    );
  }
  if (auth.error || (!auth.actor && auth.config?.mode === "oidc")) {
    if (location.pathname !== "/login") {
      const returnPath = safeAuthReturnPath(`${location.pathname}${location.search}${location.hash}`);
      return <Navigate to={`/login?returnTo=${encodeURIComponent(returnPath)}`} replace />;
    }
    return <LoginPage />;
  }
  if (location.pathname === "/login") {
    if (auth.config?.mode === "fake") return <LoginPage />;
    const returnPath = safeAuthReturnPath(new URLSearchParams(location.search).get("returnTo"));
    return <Navigate to={returnPath} replace />;
  }
  return <>
    {auth.reconciling && <p role="status">Resolving identity…</p>}
    <div key={auth.actor?.id ?? "anonymous"} inert={auth.reconciling}
      style={{ visibility: auth.reconciling ? "hidden" : undefined }}>{children}</div>
  </>;
}
