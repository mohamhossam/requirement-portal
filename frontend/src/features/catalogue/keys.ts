export const catalogueKeys = {
  me: ["me"] as const,
  releases: ["knowledge", "releases"] as const,
  active: ["knowledge", "active"] as const,
  documents: ["knowledge", "documents"] as const,
  audit: (id: string) => ["knowledge", "audit", id] as const,
  changes: (id: string) => ["knowledge", "changes", id] as const,
  suggestions: (id: string) => ["knowledge", "suggestions", id] as const,
  extractions: (id: string) => ["knowledge", "extractions", id] as const,
  build: (id: string) => ["knowledge", "build", id] as const,
  samples: ["knowledge", "samples"] as const,
  mappingImpact: ["knowledge", "mapping-impact"] as const,
  passage: (releaseId: string, versionId: string, location: string) =>
    ["knowledge", "passage", releaseId, versionId, location] as const,
  job: (id: string) => ["job", id] as const,
  organisation: ["organisation"] as const,
};
