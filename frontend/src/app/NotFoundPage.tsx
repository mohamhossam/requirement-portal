import { SearchX } from "lucide-react";

import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/shell";
import { ButtonLink } from "../components/ui/Button";
import { useDocumentTitle } from "./useDocumentTitle";

/**
 * An address that matches no page.
 *
 * It used to show the dashboard under whatever was typed, so a mistyped or
 * outdated link looked like it had worked. Saying so, with one way back, is
 * the honest answer; the old addresses that moved still redirect before this.
 */
export function NotFoundPage() {
  useDocumentTitle("Page not found");
  return (
    <>
      <PageHeader title="Page not found" />
      <EmptyState
        headingLevel="h2"
        icon={<SearchX aria-hidden="true" size={20} />}
        title="There is nothing at this address"
        message="The link may be mistyped, or the page has moved. Your requirements are on the dashboard."
        action={<ButtonLink variant="primary" to="/">Go to the dashboard</ButtonLink>}
      />
    </>
  );
}
