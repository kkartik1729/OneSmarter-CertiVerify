# Backend review: OneSmarter CertiVerify (Django + DRF + SimpleJWT)

Reviewed from `backend.zip`: every source file read, then exercised for real (Django `check`, migration drift check, 20+ API calls on SQLite, and the React frontend end-to-end against the running backend). PostgreSQL was not available here, so DB-specific behaviour was not tested.

## 1. Bugs to fix first

| # | Problem | Evidence | Fix |
|---|---|---|---|
| 1 | **Registration crashes with HTTP 500** | `accounts/migrations/0002_userprofile_totp_enabled_and_more.py` adds NOT NULL columns (`totp_enabled`, `totp_secret`, ...) but `UserProfile` has no such fields. `UserProfile.objects.create()` omits them -> `NOT NULL constraint failed: accounts_userprofile.totp_enabled`. `/me` has the same problem via `get_or_create`. `makemigrations --check` also wants a 0003 that removes them. | If TOTP/MFA is not wanted (it was excluded from this product): delete 0002 (only if never applied to your DB), otherwise add a `0003` that removes the four fields. If you do want it, add the fields to the model. |
| 2 | **Register/login do not work with an email-based form** | `RegisterSerializer` requires `username` (the settings.py comment says it is set to the email, but the code never does it). Login (`TokenObtainPairView`) needs `{"username": ..., "password": ...}`; sending `email` gives 400. | In `RegisterSerializer.validate()` set `attrs["username"] = attrs["email"].lower()` and make `username` optional. The frontend already sends `username = email`. |
| 3 | **Duplicate emails are allowed** | Two accounts with the same email registered fine (201). | Validate `email` uniqueness (case-insensitive) in `RegisterSerializer`. |
| 4 | **`/accounts/me/` reports the wrong role for superusers/staff** | A superuser without a profile row got `"role": "USER"` although `is_certiverify_admin()` treats them as admin, so the SPA shows them the user dashboard. | Return the effective role: `ADMIN` if `is_certiverify_admin(user)` else the profile role. |
| 5 | Name cannot be edited | `first_name` / `last_name` are `read_only` in `UserProfileSerializer`; PATCH silently ignores them. | Make them writable (map to `user.*`) if you want a profile name form. |
| 6 | Uploaded files probably cannot be opened | `config/urls.py` does not serve `MEDIA_URL` in DEBUG. (From reading the code; not browser-tested.) | `urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)` when `DEBUG`, and a real file server in production. |

## 2. Design conflicts with the product rules in your brief

1. **Manual approval exists.** `PATCH /certificates/<id>/review/` lets an admin set `VERIFIED` / `REJECTED`. The brief says admins must never approve, reject or change verification results. The frontend does **not** expose this endpoint. Decide: remove it, or relax the rule.
2. **Uploads are the records.** There is no separate trusted-records store: a user's upload *is* the record, `certificate_number` is globally unique, and `authentic = (status == VERIFIED)`. So any user can claim an ID first (squatting), and "verified" depends on an admin clicking approve rather than on a trusted import. Recommended: a `TrustedRecord` model filled only by an authorized import/issuer API, with the user's `Certificate` compared against it.
3. **Public verify leaks data and is unthrottled.** `GET /certificates/verify/<number>/` is anonymous and returns `recipient_name`, with no throttling and no audit log, so IDs can be enumerated. Add DRF throttling, write an audit event per lookup, and return the minimum fields.
4. The field name `authentic` overclaims. Prefer a neutral `record_status`.

## 3. Endpoints the frontend needs but the backend does not have

The `verification`, `audit`, `notifications` and `dashboard` apps exist but have empty `urls.py` and models. The frontend shows an honest "not implemented on the backend yet" card for each. When you add one, set its flag to `true` in `src/services/endpoints.ts` (`CAN`) and adapt the path/mapper.

| Feature | Suggested endpoint | Notes |
|---|---|---|
| Verification history (user) | `GET /verification/history/` | needs a `VerificationLog` model written by the verify view |
| Notifications | `GET /notifications/`, `POST /notifications/<id>/read/`, `POST /notifications/read-all/` | |
| Delete own certificate | `DELETE /certificates/<id>/` | `CertificateDetailView` is Retrieve-only today (405) |
| Change password | `POST /accounts/change-password/` | |
| Admin: users | `GET /admin/users/`, `PATCH /admin/users/<id>/ {is_active}` | |
| Admin: logs / analytics / security | `GET /audit/verification-logs/`, `/dashboard/analytics/?days=`, `/audit/security-events/` | |
| Admin: import trusted records | `POST /admin/trusted-records/import/` | with per-row error report |
| Logout / token revoke | add `rest_framework_simplejwt.token_blacklist` | refresh tokens cannot be revoked today |

Already supported and wired: register, login (JWT), `/me` (GET, PATCH phone/organization), certificate list/create/detail, public verify, and admins seeing all certificate records.

## 4. Security and hygiene

- **`backend.zip` contained `.env` (DB password, secret key) and a ~5,000-file `venv/`.** Do not share these; rotate the DB password and `DJANGO_SECRET_KEY` if the zip went anywhere public. Add both to `.gitignore`.
- `DEBUG` defaults to `True` and `SECRET_KEY` has an insecure fallback: fail fast in production if unset.
- No pagination on certificate lists (add `DEFAULT_PAGINATION_CLASS`).
- Upload validation checks the extension and 5 MB only, not the real file type.
- CORS allows only `localhost:5173-5175`: add your production origin. JWT in a header means no CSRF setup is needed.
- No automated tests exist (`tests.py` files are empty).

## 5. What was verified against the running backend

Register -> login -> `/me` -> upload (multipart) -> list -> duplicate/blank-field errors -> public verify (404 and PENDING) -> role denial on `/review/` -> admin sees all records, all driven through the real React app. By design, with default settings the JWT lives in memory, so a full page reload signs you out (`VITE_PERSIST_SESSION=true` keeps the refresh token in sessionStorage, an XSS trade-off).
