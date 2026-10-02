---
version: 1
slug: "s-catalogue-architecturecataloguepage-tsx-3d41a153"
primary_target: "frontend/src/features/catalogue/ArchitectureCataloguePage.tsx"
related_targets: ["frontend/src/features/catalogue/CatalogueBrowser.tsx","frontend/src/features/catalogue/DraftJourney.tsx","frontend/src/features/catalogue/DependencyMatrix.tsx"]
---

# Architecture catalogue

Mode: Operate. Whole-surface redesign inside the settled Working Paper world (DESIGN.md unchanged).
Serves reading the landscape and maintaining a version equally. Scope: page frame, systems
browser, version-in-progress workflow (content, review, build, publish) and version history.
User rejects: a long scroll, too much explanatory text, an unclear next step, unseen dependencies.
Presentation only: queries, mutations, keys and step-completion logic stay as they are.

## Direction contract

THESIS: One workbench, two versions, multiple views, one controlled change workflow. Refuses the
stacked-card page where the systems hide behind a disclosure and the draft sinks below it.

OWN-WORLD: Working Paper tokens only: paper canvas, white sheet panels, hairlines, one indigo
accent spent on the open step / NEXT, amber for outdated mappings, green/red + words for
added/removed. Segmented switches on sunken ground; the desk reuses the stage-rail grammar.

STORY: Anyone lands on the systems and can read any one's dependencies; a maintainer sees what is
live, whether a version is in progress, and the one next thing to do, without scrolling.

FIRST VIEWPORT: Title and catalogue tabs; below, a two-region grid. Left (fluid): toolbar with the
version switch (In use | In progress) and view switch (Systems | Dependencies | History), then
the view: index (sticky, own scroll) + dossier, or the matrix, or history, or an open step.
Right (300px, sticky): the Change desk: live version, the version in progress as four
stage-rail steps, NEXT block, rename/remove; or Start a new version.

FORM: Grounded fusion locked by the user (seed 51995cf8, dealt 5/7/2; user combined 2+1+3).
Signature interaction: the dependency matrix with crosshair and added/removed cell marks.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance.
