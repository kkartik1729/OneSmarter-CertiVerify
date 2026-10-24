/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_API_URL?: string;
  readonly VITE_API_TIMEOUT_MS?: string;
  readonly VITE_TEMPLATE_UPLOAD_TIMEOUT_MS?: string;
  readonly VITE_CSV_VALIDATION_TIMEOUT_MS?: string;
  readonly VITE_BULK_GENERATION_TIMEOUT_MS?: string;
  readonly VITE_CERTIFICATE_GENERATION_TIMEOUT_MS?: string;
  readonly VITE_GOOGLE_CLIENT_ID?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
