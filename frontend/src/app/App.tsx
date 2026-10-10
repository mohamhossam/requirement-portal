import { lazy, Suspense } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import { AppShell } from "../components/shell";
import { ErrorBoundary, LoadingState } from "../components/states";
import { DashboardPage } from "./DashboardPage";
import { LegacyEvidenceLink, LegacyLibraryLink } from "./legacyKnowledgeLinks";
import { NotFoundPage } from "./NotFoundPage";
import { RequirementEntryRedirect } from "./RequirementEntryRedirect";

/**
 * What ships in the first request, and what waits until it is asked for.
 *
 * The dashboard is the landing route and the fallback for anything unmatched, and
 * the entry redirect is what a bare Requirement link lands on, so both stay in
 * the initial bundle. Everything else is a destination somebody navigates to: the
 * whole app used to arrive in one 583 kB chunk, which meant every reviewer
 * downloaded Reports, Activity, the intake form and the entire Backlog workspace
 * before they could look at a worklist.
 *
 * The Requirement workspace is one lazy unit rather than seven, because the seven
 * stage routes are the same component and a person walks straight through them.
 */
const ActivityPage = lazy(() => import("./ActivityPage").then((m) => ({ default: m.ActivityPage })));
const ReportsPage = lazy(() => import("./ReportsPage").then((m) => ({ default: m.ReportsPage })));
const NewRequirementPage = lazy(() => import("./NewRequirementPage").then((m) => ({ default: m.NewRequirementPage })));
const DocumentsPage = lazy(() => import("./DocumentsPage").then((m) => ({ default: m.DocumentsPage })));
const DocumentDetailPage = lazy(() => import("./DocumentDetailPage").then((m) => ({ default: m.DocumentDetailPage })));
const RequirementPage = lazy(() => import("./RequirementPage").then((m) => ({ default: m.RequirementPage })));
const ReferencePassagePage = lazy(() => import("./ReferencePassagePage").then((m) => ({ default: m.ReferencePassagePage })));
const ArchitectureEvidencePage = lazy(() => import("./ArchitectureEvidencePage").then((m) => ({ default: m.ArchitectureEvidencePage })));

/**
 * The shell wraps the router, not each route.
 *
 * Seven pages used to render their own `<div className="app-shell">`, their own
 * header and their own `<main>`, and they disagreed about all three — which is
 * how the product ended up with three navigation systems (docs/ux-plan.md §3.1)
 * and a Backlog route that looked like a different product (§3.3). Hoisting it
 * here makes that structurally impossible, and it fixes the chunk-loading gap for
 * free: the header and the navigation stay on screen while a lazy route arrives,
 * instead of the whole window going blank.
 */
export function App() {
  // Navigating away from a page that crashed leaves the crash behind.
  const { pathname } = useLocation();
  return (
    <AppShell>
      <ErrorBoundary resetKey={pathname} scope="route">
        <Suspense fallback={<LoadingState label="Opening the page" variant="page" />}>
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/activity" element={<ActivityPage />} />
            <Route path="/reports" element={<ReportsPage />} />
            <Route path="/requirements/new" element={<NewRequirementPage />} />
            <Route path="/documents" element={<DocumentsPage />} />
            {/* The library and the catalogues moved to the knowledge portal (ADR-0099). Old links
                to a cited passage or to evidence still open, in this app's read-only views. */}
            <Route path="/documents/library" element={<Navigate to="/documents" replace />} />
            <Route path="/documents/library/:libraryId" element={<LegacyLibraryLink />} />
            <Route path="/documents/:documentId" element={<DocumentDetailPage />} />
            <Route path="/references/passage" element={<ReferencePassagePage />} />
            <Route path="/architecture-evidence/:releaseId/:chunkId" element={<ArchitectureEvidencePage />} />
            <Route path="/architecture-knowledge/releases/:releaseId/evidence/:chunkId" element={<LegacyEvidenceLink />} />
            <Route path="/architecture-knowledge/*" element={<Navigate to="/documents" replace />} />
            <Route path="/requirements/:id" element={<RequirementEntryRedirect />} />
            <Route path="/requirements/:id/capture" element={<RequirementPage view="capture" />} />
            <Route path="/requirements/:id/clarify" element={<RequirementPage view="clarify" />} />
            <Route path="/requirements/:id/knowledge" element={<RequirementPage view="knowledge" />} />
            <Route path="/requirements/:id/confirm" element={<RequirementPage view="confirm" />} />
            <Route path="/requirements/:id/breakdown" element={<RequirementPage view="breakdown" />} />
            <Route path="/requirements/:id/breakdown/epic" element={<RequirementPage view="breakdown" />} />
            <Route path="/requirements/:id/breakdown/features/:featureId" element={<RequirementPage view="breakdown" />} />
            <Route path="/requirements/:id/breakdown/features/:featureId/stories/:storyId" element={<RequirementPage view="breakdown" />} />
            <Route path="/requirements/:id/revisions" element={<RequirementPage view="revisions" />} />
            <Route path="/requirements/:id/review" element={<RequirementPage view="review" />} />
            {/* After an OIDC sign-in the address is rewritten outside the router
                (AuthProvider's `replaceState`), so the router can still be on the
                callback path. It lands on the dashboard, as it always has, not on
                "Page not found". */}
            <Route path="/auth/*" element={<DashboardPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </Suspense>
      </ErrorBoundary>
    </AppShell>
  );
}
