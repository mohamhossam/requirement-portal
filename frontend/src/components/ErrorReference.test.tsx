import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ApiError, errorReference } from "../api/errors";
import { ErrorNotice } from "./ErrorNotice";
import { ErrorState } from "./states/ErrorState";

describe("error references", () => {
  it("are the API's correlation ID, and nothing for a failure that never reached it", () => {
    expect(errorReference(new ApiError(503, "Busy.", "database_busy", "req-7f3a"))).toBe("req-7f3a");
    expect(errorReference(new ApiError(0, "Failed to fetch"))).toBeNull();
    expect(errorReference(new Error("boom"))).toBeNull();
    expect(errorReference(null)).toBeNull();
  });

  it("appear under an ErrorState's message, as one selectable ID", () => {
    render(<ErrorState message="The database is busy." reference="req-7f3a" />);
    expect(screen.getByRole("alert")).toHaveTextContent("Reference: req-7f3a");
    expect(screen.getByText("req-7f3a").tagName).toBe("CODE");
  });

  it("appear under an ErrorNotice's message", () => {
    render(<ErrorNotice message="The database is busy." reference="req-7f3a" />);
    expect(screen.getByRole("alert")).toHaveTextContent("Reference: req-7f3a");
  });

  it("are left out when there is none", () => {
    render(<ErrorState message="The API is unavailable." reference={null} />);
    expect(screen.getByRole("alert")).not.toHaveTextContent("Reference");
  });
});
