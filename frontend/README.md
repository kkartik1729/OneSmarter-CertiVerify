# OneSmarter CertiVerify: React frontend

React 18 + TypeScript (strict) + Vite + React Router. Dark navy/blue theme.

## Run
```bash
npm install
npm run dev        # http://localhost:5173
npm run build      # type-check + production build into dist/
npm run preview    # serve the production build
```

## Demo mode (default)
With no `VITE_API_URL`, the app runs on isolated sample data (`src/services/demo.ts`). Nothing is sent to a server and data resets on reload.
- Admin: `admin@demo.com` -> `/admin` (any password, 8+ chars)
- User: any `@demo.com` / `@demo.test` email, or an account you register in the session -> `/dashboard`
- Lookup IDs: `OSC-2026-00125` (found), `OSC-2024-99999` (not found), `ERR-0000-00000` (service error)

## Connect the Django REST backend
Copy `.env.example` to `.env` and set `VITE_API_URL=https://your-api.example.com/api`. `src/services/api.ts` then uses these contracts (cookie/session auth via `credentials: 'include'`; no tokens or passwords are kept in browser storage):
- `POST /auth/login {email,password}` -> `User {name,email,role}`; `POST /auth/register {name,email,password}` (server must force role `user`)
- `POST /verify {certificate_id}` -> `{found:boolean, record?:Trusted}`; non-2xx = Service Error (never a "not found")

## Structure
```
src/
  components/  Shell (sidebar/topbar/drawer), Guard, DataTable, VerifyBox, HeroArt
  context/     Auth (session user), Data (demo state: certificates, history, notifications, users)
  lib/         ui (Icon, Badge, toast, confirm dialog), nav, content
  pages/       Home, Auth (login/register), User (8 pages), Admin (7 pages), Misc (404/403)
  services/    api.ts (real calls + demo fallback), demo.ts (isolated sample data)
```

## Rules the UI follows
- A record match is never presented as proof an uploaded file is authentic; "ID Not Found" is never called fake.
- Uploads never become trusted records. Admin has no approve/reject/mark-genuine controls; logs are read-only.
- Route guards are UX only; the backend must enforce authorization.

## Still needs backend endpoints (currently demo-only)
Certificates CRUD (`/certificates`), `/verify/history`, `/me`, `/notifications`, `/admin/users`, `/admin/trusted-records` (+ import), `/admin/verification-logs`, `/admin/analytics`, `/admin/security-events`, `/admin/settings`.
