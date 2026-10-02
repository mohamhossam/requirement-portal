import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { renderWithClient } from "../../test/renderWithClient";
import { NotificationCenter } from "./NotificationCenter";

describe("NotificationCenter", () => {
  afterEach(() => vi.restoreAllMocks());

  it("enables browser notifications only after explicit opt-in", async () => {
    vi.spyOn(api, "listNotifications").mockResolvedValue([]);
    vi.spyOn(api, "getNotificationPreference").mockResolvedValue({ browser_enabled: false });
    const save = vi.spyOn(api, "setNotificationPreference").mockResolvedValue({
      browser_enabled: true,
    });
    const requestPermission = vi.fn().mockResolvedValue("granted");
    Object.defineProperty(globalThis, "Notification", {
      configurable: true,
      value: { permission: "default", requestPermission },
    });

    renderWithClient(<MemoryRouter><NotificationCenter /></MemoryRouter>);
    await userEvent.click(screen.getByRole("button", { name: "Notifications" }));
    await userEvent.click(await screen.findByRole("button", { name: "Enable browser alerts" }));

    await waitFor(() => expect(save).toHaveBeenCalledWith(true));
    expect(requestPermission).toHaveBeenCalledOnce();
  });
});
