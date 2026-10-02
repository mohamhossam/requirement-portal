import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { api, configureAuthentication, type IdentityConfig } from "../api/client";
import { AppTopBar } from "../components/shell";
import { AuthGate, AuthProvider } from "./AuthProvider";
import { useAuth } from "./authContext";
import { safeAuthReturnPath } from "./returnPath";

const oidc = vi.hoisted(() => {
  const manager = {
    getUser: vi.fn(),
    signinRedirect: vi.fn(),
    signinRedirectCallback: vi.fn(),
    signinSilentCallback: vi.fn(),
    signinSilent: vi.fn(),
    signoutRedirect: vi.fn(),
    events: {
      addUserLoaded: vi.fn(),
      removeUserLoaded: vi.fn(),
    },
  };
  return { manager };
});

vi.mock("oidc-client-ts", () => ({
  UserManager: vi.fn(function UserManager() { return oidc.manager; }),
  WebStorageStateStore: vi.fn(function WebStorageStateStore() { return {}; }),
}));

const owner = { id: "fake-owner", display_name: "Amina Owner", email: "amina@example.test" };
const reviewer = { id: "fake-reviewer", display_name: "Ravi Reviewer", email: "ravi@example.test" };

const oidcConfig: IdentityConfig = {
  mode: "oidc" as const,
  authority: "https://identity.example.test/realms/requirement-ai",
  audience: "requirement-api",
  client_id: "requirement-spa",
  scopes: "openid profile email",
  fake_actors: [],
  login_choices: [
    { id: "microsoft", label: "Continue with Microsoft", authorization_parameters: { kc_idp_hint: "company-sso" } },
    { id: "password", label: "Continue with email and password", authorization_parameters: {} },
  ],
};

beforeEach(() => {
  sessionStorage.clear();
  window.history.replaceState({}, "", "/");
  oidc.manager.getUser.mockReset().mockResolvedValue(null);
  oidc.manager.signinRedirect.mockReset().mockResolvedValue(undefined);
  oidc.manager.signinRedirectCallback.mockReset();
  oidc.manager.signinSilentCallback.mockReset();
  oidc.manager.signinSilent.mockReset();
  oidc.manager.signoutRedirect.mockReset();
  oidc.manager.events.addUserLoaded.mockReset();
  oidc.manager.events.removeUserLoaded.mockReset();
});
afterEach(() => {
  vi.restoreAllMocks();
  configureAuthentication(() => ({}));
});

function TestLocation() {
  return <output aria-label="location">{useLocation().pathname}{useLocation().search}</output>;
}

function SignOutButton() {
  const auth = useAuth();
  return <button type="button" onClick={() => void auth?.signOut()}>Sign out now</button>;
}

it("redirects a protected deep link to the branded login page", async () => {
  vi.spyOn(api, "getIdentityConfig").mockResolvedValue(oidcConfig);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <AuthProvider>
        <MemoryRouter initialEntries={["/requirements/abc/confirm?tab=evidence"]}>
          <AuthGate><p>Protected workspace</p></AuthGate>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );

  expect(await screen.findByRole("heading", { name: "Welcome back" })).toBeInTheDocument();
  expect(screen.queryByText("Protected workspace")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Continue with Microsoft" })).toBeEnabled();
});

it("starts each configured OIDC choice and preserves a safe return path", async () => {
  vi.spyOn(api, "getIdentityConfig").mockResolvedValue(oidcConfig);
  window.history.replaceState({}, "", "/login?returnTo=%2Frequirements%2Fabc%2Fconfirm%3Ftab%3Devidence");
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <AuthProvider>
        <MemoryRouter initialEntries={["/login?returnTo=%2Frequirements%2Fabc%2Fconfirm%3Ftab%3Devidence"]}>
          <AuthGate><p>Protected workspace</p></AuthGate>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );

  await userEvent.click(await screen.findByRole("button", { name: "Continue with Microsoft" }));
  expect(oidc.manager.signinRedirect).toHaveBeenCalledWith({
    extraQueryParams: { kc_idp_hint: "company-sso" },
  });
  expect(sessionStorage.getItem("requirement-ai.auth-return-path"))
    .toBe("/requirements/abc/confirm?tab=evidence");

  await userEvent.click(screen.getByRole("button", { name: "Continue with email and password" }));
  expect(oidc.manager.signinRedirect).toHaveBeenLastCalledWith({ extraQueryParams: {} });
});

it("shows a recoverable redirect error and does not start duplicate redirects", async () => {
  vi.spyOn(api, "getIdentityConfig").mockResolvedValue(oidcConfig);
  let rejectRedirect: (reason: Error) => void = () => undefined;
  oidc.manager.signinRedirect.mockImplementation(() => new Promise((_, reject) => {
    rejectRedirect = reject;
  }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <AuthProvider><MemoryRouter initialEntries={["/login"]}><AuthGate><p>Workspace</p></AuthGate></MemoryRouter></AuthProvider>
    </QueryClientProvider>,
  );

  const microsoft = await screen.findByRole("button", { name: "Continue with Microsoft" });
  await userEvent.click(microsoft);
  expect(screen.getByRole("button", { name: "Continue with email and password" })).toBeDisabled();
  await userEvent.click(screen.getByRole("button", { name: "Continue with email and password" }));
  expect(oidc.manager.signinRedirect).toHaveBeenCalledTimes(1);
  rejectRedirect(new Error("The sign-in window was cancelled."));
  expect(await screen.findByText("The sign-in window was cancelled.")).toBeInTheDocument();
});

it("shows the labelled local persona entry on the login route", async () => {
  vi.spyOn(api, "getIdentityConfig").mockResolvedValue({
    mode: "fake",
    authority: null,
    audience: null,
    client_id: null,
    scopes: null,
    fake_actors: [owner, reviewer],
    login_choices: [],
  });
  vi.spyOn(api, "getCurrentActor").mockResolvedValue(owner);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <AuthProvider><MemoryRouter initialEntries={["/login"]}><AuthGate><p>Workspace</p></AuthGate></MemoryRouter></AuthProvider>
    </QueryClientProvider>,
  );

  expect(await screen.findByText("Development mode")).toBeInTheDocument();
  expect(screen.getByLabelText("Test persona")).toHaveValue("fake-owner");
});

it("returns an already authenticated user from login to the safe destination", async () => {
  vi.spyOn(api, "getIdentityConfig").mockResolvedValue(oidcConfig);
  oidc.manager.getUser.mockResolvedValue({ access_token: "token", expired: false });
  vi.spyOn(api, "getCurrentActor").mockResolvedValue(owner);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <AuthProvider>
        <MemoryRouter initialEntries={["/login?returnTo=%2Freports"]}>
          <AuthGate>
            <Routes><Route path="*" element={<TestLocation />} /></Routes>
          </AuthGate>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );

  expect(await screen.findByLabelText("location")).toHaveTextContent("/reports");
});

it("rejects external and authentication-loop return destinations", () => {
  expect(safeAuthReturnPath("https://evil.example/steal")).toBe("/");
  expect(safeAuthReturnPath("/auth/callback?code=secret")).toBe("/");
  expect(safeAuthReturnPath("/login?returnTo=/reports")).toBe("/");
  expect(safeAuthReturnPath("/requirements/abc#review")).toBe("/requirements/abc#review");
});

it("completes the OIDC callback and restores the saved browser path", async () => {
  vi.spyOn(api, "getIdentityConfig").mockResolvedValue(oidcConfig);
  vi.spyOn(api, "getCurrentActor").mockResolvedValue(owner);
  oidc.manager.signinRedirectCallback.mockResolvedValue({ access_token: "token", expired: false });
  sessionStorage.setItem("requirement-ai.auth-return-path", "/reports?weeks=4#blockers");
  window.history.replaceState({}, "", "/auth/callback?code=authorization-code");
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <AuthProvider>
        <MemoryRouter initialEntries={["/auth/callback?code=authorization-code"]}>
          <AuthGate><p>Protected workspace</p></AuthGate>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );

  expect(await screen.findByText("Protected workspace")).toBeInTheDocument();
  expect(oidc.manager.signinRedirectCallback).toHaveBeenCalledOnce();
  expect(window.location.pathname).toBe("/reports");
  expect(window.location.hash).toBe("#blockers");
  expect(sessionStorage.getItem("requirement-ai.auth-return-path")).toBeNull();
});

it("clears actor-bound query state before provider logout", async () => {
  vi.spyOn(api, "getIdentityConfig").mockResolvedValue(oidcConfig);
  vi.spyOn(api, "getCurrentActor").mockResolvedValue(owner);
  oidc.manager.getUser.mockResolvedValue({ access_token: "token", expired: false });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(["private", "fake-owner"], { confidential: true });
  render(
    <QueryClientProvider client={client}>
      <AuthProvider><MemoryRouter initialEntries={["/"]}><AuthGate><SignOutButton /></AuthGate></MemoryRouter></AuthProvider>
    </QueryClientProvider>,
  );

  await userEvent.click(await screen.findByRole("button", { name: "Sign out now" }));
  expect(oidc.manager.signoutRedirect).toHaveBeenCalledOnce();
  expect(client.getQueryCache().getAll()).toHaveLength(0);
});

it("loads fake identity and switches persona without navigating away", async () => {
  vi.spyOn(api, "getIdentityConfig").mockResolvedValue({
    mode: "fake",
    authority: null,
    audience: null,
    client_id: null,
    scopes: null,
    fake_actors: [owner, reviewer],
    login_choices: [],
  });
  vi.spyOn(api, "getCurrentActor")
    .mockResolvedValueOnce(owner)
    .mockResolvedValueOnce(reviewer);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><AuthProvider><MemoryRouter initialEntries={["/requirements/1/confirm"]}><AuthGate><AppTopBar onOpenNav={() => undefined} /></AuthGate></MemoryRouter></AuthProvider></QueryClientProvider>);

  expect((await screen.findAllByText("Amina Owner")).length).toBeGreaterThan(0);
  await userEvent.selectOptions(screen.getByLabelText("Development persona"), "fake-reviewer");
  expect((await screen.findAllByText("Ravi Reviewer")).length).toBeGreaterThan(0);
  expect(sessionStorage.getItem("requirement-ai.fake-actor")).toBe("fake-reviewer");
});

it("ignores a stale remembered fake persona and loads the configured default", async () => {
  sessionStorage.setItem("requirement-ai.fake-actor", "removed-persona");
  vi.spyOn(api, "getIdentityConfig").mockResolvedValue({
    mode: "fake",
    authority: null,
    audience: null,
    client_id: null,
    scopes: null,
    fake_actors: [owner, reviewer],
    login_choices: [],
  });
  const currentActor = vi.spyOn(api, "getCurrentActor").mockResolvedValue(owner);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <AuthProvider><MemoryRouter initialEntries={["/"]}><AuthGate><p>Workspace</p></AuthGate></MemoryRouter></AuthProvider>
    </QueryClientProvider>,
  );

  expect(await screen.findByText("Workspace")).toBeInTheDocument();
  expect(currentActor).toHaveBeenCalledOnce();
  expect(sessionStorage.getItem("requirement-ai.fake-actor")).toBe("fake-owner");
});
