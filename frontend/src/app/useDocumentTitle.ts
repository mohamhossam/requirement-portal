import { useEffect } from "react";

/**
 * What the tab, the window switcher and the screen reader call this page.
 *
 * A single-page app keeps the `<title>` it was served with unless something
 * changes it, so all eight routes announced "SMB Requirement Review" — a name
 * the product no longer uses, and one that told a reviewer with four
 * Requirements open in four tabs nothing about which was which. A screen
 * reader takes the title as its confirmation that navigation happened, so a
 * static one means every route change is silent.
 *
 * Pass the page's own name. The product name is appended here so no caller has
 * to remember it, and the suffix alone is used when a page has nothing more
 * specific to say yet (a pending load, an error).
 */
const PRODUCT = "Requirement AI";

export function useDocumentTitle(title: string | null | undefined): void {
  useEffect(() => {
    const trimmed = title?.trim();
    document.title = trimmed ? `${trimmed} · ${PRODUCT}` : PRODUCT;
  }, [title]);
}
