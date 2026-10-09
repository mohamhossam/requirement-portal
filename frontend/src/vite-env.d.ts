/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
  readonly VITE_KNOWLEDGE_PORTAL_URL?: string;
  readonly VITE_KNOWLEDGE_PORTAL_ROLE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
