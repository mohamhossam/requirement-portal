import { expect, it } from "vitest";
import { jobError } from "./labels";

it("says why reading a document failed, in words", () => {
  expect(jobError("catalogue_extraction_uncited")).toMatch(/none of its suggestions quoted the document/);
  expect(jobError("catalogue_extraction_unusable")).toMatch(/even when asked twice/);
  expect(jobError("model_rate_limit")).toMatch(/rate limit was reached/);
  expect(jobError("not_a_known_code")).toBe("something went wrong on the server");
  expect(jobError(null)).toBeNull();
});
