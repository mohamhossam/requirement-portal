import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import type { IdentityConfig } from "../api/client";
import { AuthContext, type AuthState } from "./authContext";
import { LoginPage } from "./LoginPage";

const fakeConfig: IdentityConfig = {
  mode: "fake",
  authority: null,
  audience: null,
  client_id: null,
  scopes: null,
  fake_actors: [
    { id: "fake-owner", display_name: "Amina Owner", email: null },
    { id: "fake-reviewer", display_name: "Rami Reviewer", email: null },
  ],
  login_choices: [],
};

const oidcConfig: IdentityConfig = {
  ...fakeConfig,
  mode: "oidc",
  authority: "https://identity.example/realm",
  client_id: "requirement-spa",
  fake_actors: [],
  login_choices: [
    { id: "microsoft", label: "Sign in with Microsoft" },
    { id: "password", label: "Sign in with a password" },
  ] as IdentityConfig["login_choices"],
};

const baseAuth: AuthState = {
  actor: { id: "fake-owner", display_name: "Amina Owner", email: null },
  config: fakeConfig,
  loading: false,
  reconciling: false,
  error: null,
  sessionExpired: false,
  signingInChoice: null,
  callbackReturnPath: null,
  signIn: vi.fn().mockResolvedValue(undefined),
  signOut: vi.fn().mockResolvedValue(undefined),
  switchFakeActor: vi.fn().mockResolvedValue(undefined),
};

function renderLogin(auth: AuthState, initialEntry = "/login") {
  return render(
    <AuthContext.Provider value={auth}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="*" element={<p>At {initialEntry}</p>} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  );
}

describe("LoginPage", () => {
  it("offers the development personas in fake mode and continues to the safe return path", async () => {
    renderLogin(baseAuth, "/login?returnTo=/requirements/req-9/clarify");
    expect(screen.getByText("Development mode")).toBeInTheDocument();
    const select = screen.getByLabelText("Test persona");
    expect(select).toHaveValue("fake-owner");

    await userEvent.selectOptions(select, "fake-reviewer");
    expect(baseAuth.switchFakeActor).toHaveBeenCalledWith("fake-reviewer");

    await userEvent.click(screen.getByRole("button", { name: "Continue to workspace" }));
    expect(await screen.findByText("At /login?returnTo=/requirements/req-9/clarify")).toBeInTheDocument();
  });

  it("never follows a cross-origin returnTo", async () => {
    renderLogin(baseAuth, "/login?returnTo=https://evil.example/phish");
    await userEvent.click(screen.getByRole("button", { name: "Continue to workspace" }));
    // The catch-all route rendered for "/" — not an external redirect target.
    expect(await screen.findByText(/^At /)).toBeInTheDocument();
  });

  it("offers each configured OIDC sign-in choice", async () => {
    const auth = { ...baseAuth, actor: null, config: oidcConfig };
    renderLogin(auth);
    await userEvent.click(screen.getByRole("button", { name: "Sign in with Microsoft" }));
    expect(auth.signIn).toHaveBeenCalledWith("microsoft");
    expect(screen.getByRole("button", { name: "Sign in with a password" })).toBeInTheDocument();
  });

  it("names a failed sign-in and an expired session differently", () => {
    const { rerender } = renderLogin({ ...baseAuth, error: "The identity provider refused." });
    expect(screen.getByRole("alert")).toHaveTextContent("We couldn’t sign you in");

    rerender(
      <AuthContext.Provider
        value={{ ...baseAuth, error: "Sign in again.", sessionExpired: true }}
      >
        <MemoryRouter initialEntries={["/login"]}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
          </Routes>
        </MemoryRouter>
      </AuthContext.Provider>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Your session ended");
  });

  it("offers a reload when the identity configuration never arrived", async () => {
    const reload = vi.fn();
    vi.spyOn(window, "location", "get").mockReturnValue({
      ...window.location,
      reload,
    } as unknown as Location);
    renderLogin({ ...baseAuth, actor: null, config: null });
    await userEvent.click(screen.getByRole("button", { name: "Try loading sign-in again" }));
    expect(reload).toHaveBeenCalled();
    vi.restoreAllMocks();
  });
});
