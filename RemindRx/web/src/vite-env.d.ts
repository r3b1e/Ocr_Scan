/// <reference types="vite/client" />

interface ImportMetaEnv {
    /** Base URL of the prescription-extraction service (python -m service). */
    readonly VITE_EXTRACT_API?: string;
}

interface ImportMeta {
    readonly env: ImportMetaEnv;
}
