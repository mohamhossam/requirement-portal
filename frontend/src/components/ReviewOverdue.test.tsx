import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ReviewOverdue } from "./ReviewOverdue";
import { reviewOverdue } from "./reviewDates";

describe("ReviewOverdue", () => {
  it("is overdue from the start of its due day, and not before", () => {
    expect(reviewOverdue("2026-10-01", new Date("2026-10-01T00:00:00Z"))).toBe(true);
    expect(reviewOverdue("2026-10-01", new Date("2026-09-30T23:59:59Z"))).toBe(false);
    expect(reviewOverdue(null)).toBe(false);
    expect(reviewOverdue(undefined)).toBe(false);
  });

  it("flags a source whose review date has passed, and says nothing otherwise", () => {
    const { rerender, container } = render(<ReviewOverdue dueOn="2020-01-02" subject="system" />);
    const label = screen.getByText(/Review overdue since/);
    expect(label).toHaveTextContent(/2020/);
    expect(label).toHaveTextContent(/the knowledge portal has not re-confirmed this system since\.$/);
    rerender(<ReviewOverdue dueOn="2999-01-01" />);
    expect(container).toBeEmptyDOMElement();
    rerender(<ReviewOverdue dueOn={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});
