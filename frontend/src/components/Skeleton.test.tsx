import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Skeleton } from "./Skeleton";

describe("Skeleton", () => {
  it("announces what is loading through a status role", () => {
    render(<Skeleton label="Loading the analysis" />);
    expect(screen.getByRole("status", { name: "Loading the analysis" })).toBeInTheDocument();
  });

  it("keeps the shimmer itself out of the accessibility tree", () => {
    const { container } = render(<Skeleton label="Loading Stories" />);
    const bars = container.querySelectorAll('[role="status"] > span[aria-hidden]');
    expect(bars.length).toBeGreaterThan(0);
    bars.forEach((bar) => expect(bar).toHaveAttribute("aria-hidden", "true"));
  });

  it("shapes itself to what is coming", () => {
    const { container, rerender } = render(<Skeleton label="Loading" variant="row" />);
    expect(container.querySelector('[data-variant="row"]')).toBeInTheDocument();
    expect(container.querySelectorAll("span[aria-hidden]")).toHaveLength(5);

    rerender(<Skeleton label="Loading" variant="inline" />);
    expect(container.querySelector('[data-variant="inline"]')).toBeInTheDocument();
    expect(container.querySelectorAll("span[aria-hidden]")).toHaveLength(1);

    rerender(<Skeleton label="Loading" variant="page" />);
    expect(container.querySelector('[data-variant="page"]')).toBeInTheDocument();
  });

  it("takes an explicit bar count for panels that are not three lines deep", () => {
    const { container } = render(<Skeleton label="Loading the approval workflow" bars={2} />);
    expect(container.querySelectorAll("span[aria-hidden]")).toHaveLength(2);
  });
});
