# OneSmarter CertiVerify frontend

React 18, TypeScript, Vite, and React Router client for the Django REST API.

## Development

```bash
npm install
npm run dev       # http://localhost:5173
npm run build     # TypeScript check and production build in dist/
npm run preview   # preview the production build
```

The Vite development server proxies `/api` to Django. The default target is
`http://127.0.0.1:8000`; set `DEV_API_PROXY_TARGET` when the backend runs at a
different address. Keep the browser and Django CORS/CSRF origin settings aligned
when connecting directly to a remote API.

## API configuration

Copy `.env.example` to `.env` for local configuration. `VITE_API_BASE_URL`
defaults to `/api`; the HTTP client adds `/api` when a host URL omits it. For
example, use `VITE_API_BASE_URL=https://api.example.com` or
`VITE_API_BASE_URL=https://api.example.com/api`.

Optional client settings:

- `VITE_API_TIMEOUT_MS` — standard request timeout (default 15 seconds).
- `VITE_CERTIFICATE_GENERATION_TIMEOUT_MS` — single generation timeout.
- `VITE_BULK_GENERATION_TIMEOUT_MS` — bulk generation timeout.
- `VITE_TEMPLATE_UPLOAD_TIMEOUT_MS` — template upload timeout.
- `VITE_CSV_VALIDATION_TIMEOUT_MS` — CSV validation timeout.
- `VITE_GOOGLE_CLIENT_ID` — Google Sign-In client ID.

Authentication uses the Django account and JWT endpoints. Access and refresh
tokens are held in `sessionStorage` for the current browser tab; logout and
session expiry clear them. The backend remains responsible for authentication,
authorization, email verification, and certificate status decisions.

## Main areas

- `src/pages/` — public verification, account flows, user pages, and admin pages.
- `src/components/` — shared page, certificate, form, and viewer components.
- `src/context/AuthContext.tsx` — authenticated user state and restore flow.
- `src/services/` — HTTP client, endpoint paths, API methods, and response mappers.
- `src/lib/` — date, download, media, navigation, and UI helpers.

Public verification is available at `/verify-certificate/:certificateNumber`
and `/verify-certificate`. Certificate and admin APIs require the permissions
enforced by Django; frontend route guards are only a user experience layer.
