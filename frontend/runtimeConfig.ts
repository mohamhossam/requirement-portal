import type { Plugin } from "vite";

/**
 * The values the web container renders into `index.html` when it starts
 * (`deploy/web/render-index.sh`), so one image serves every deployment. The app
 * reads them back from these `<meta>` tags (`src/api/knowledge.ts`).
 */
export const RUNTIME_VALUES = {
  "knowledge-portal-url": "__KNOWLEDGE_PORTAL_URL__",
  "knowledge-portal-role": "__KNOWLEDGE_PORTAL_ROLE__",
} as const;

/** Adds a placeholder `<meta>` for each runtime value; only the container image's build uses it. */
export function runtimeConfig(enabled: boolean): Plugin {
  return {
    name: "runtime-config",
    apply: "build",
    transformIndexHtml(html) {
      if (!enabled) return html;
      const tags = Object.entries(RUNTIME_VALUES)
        .map(([name, placeholder]) => `<meta name="${name}" content="${placeholder}" />`)
        .join("\n    ");
      return html.replace(/<\/head>/i, `    ${tags}\n  </head>`);
    },
  };
}
