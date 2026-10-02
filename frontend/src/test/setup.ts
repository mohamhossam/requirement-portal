import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// jsdom implements <dialog> but not showModal/close. Every modal in the app now
// goes through components/Modal, so the shim belongs here rather than in each
// test file that happens to open one. It only sets the `open` attribute, which
// is what makes the dialog visible to queries; the top layer, focus trapping
// and ::backdrop are browser behaviour the Playwright suite covers.
if (typeof HTMLDialogElement.prototype.showModal !== "function") {
  Object.defineProperty(HTMLDialogElement.prototype, "showModal", {
    configurable: true,
    value(this: HTMLDialogElement) { this.setAttribute("open", ""); },
  });
  Object.defineProperty(HTMLDialogElement.prototype, "close", {
    configurable: true,
    value(this: HTMLDialogElement) { this.removeAttribute("open"); },
  });
}

afterEach(() => {
  cleanup();
  localStorage.clear();
});
