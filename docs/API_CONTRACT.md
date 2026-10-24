# API contract

Base path: `/api/`. JSON endpoints use trailing slashes. Unless an endpoint is
listed as public, it requires `Authorization: Bearer <access-token>`. Public
certificate lookup and authentication endpoints accept anonymous requests.

Errors use DRF's JSON error format. Protected endpoints return `401` for a
missing or invalid session and `403` when an authenticated account lacks the
required role or email verification. Request and response bodies should be
treated as JSON unless a file upload/download is documented below.

## Accounts (`/api/accounts/`)

| Method | Path | Access | Purpose |
|---|---|---|---|
| POST | `register/` | Public | Create account and send email verification code. |
| POST | `verify-email/` | Public | Verify an account using its code or link token. |
| POST | `resend-verification/` | Public | Resend verification instructions (generic response). |
| POST | `login/` | Public | Password login; may return an MFA challenge instead of JWTs. |
| POST | `google-login/`, `google/` | Public | Verify Google credential and sign in. |
| POST | `token/refresh/` | Public | Refresh a JWT after token, account, verification, and activity checks. |
| GET/PATCH | `me/` | Authenticated | Read profile or update supported profile fields. |
| POST | `mfa/setup/`, `mfa/confirm/`, `mfa/verify/` | Authenticated/challenge | Configure or complete MFA. |
| POST | `mfa/recovery/request/`, `confirm/`, `complete/` | Public | Recover MFA by email and enroll a replacement authenticator. |
| POST | `password-reset/request/`, `validate/`, `complete/` | Public | Request, validate, and consume a password reset token. |
| POST | `set-password/` | Authenticated | Set a local password on an eligible Google account. |
| GET | `admin/users/`, `admin/users/{id}/` | Admin | List or inspect accounts. |

## Certificates (`/api/certificates/`)

| Method | Path | Access | Purpose |
|---|---|---|---|
| GET/POST | `/` | Authenticated/admin for issuance | List owned certificates or create an eligible record. |
| GET | `verify/{certificate_number}/` | Public | Check the record and its current status. |
| GET | `verify/{certificate_number}/preview/` | Public | Preview a certificate when policy allows. |
| GET/PATCH/DELETE | `{id}/` | Owner/admin | Read or manage an authorized record. |
| POST | `{id}/review/` | Admin | Change verification status with review reason. |
| GET/POST | `courses/` | Admin for writes | List or manage issuance courses. |
| GET/PATCH/DELETE | `courses/{id}/` | Admin | Manage a course. |
| GET/POST | `templates/` | Admin | List/upload templates. Multipart uploads use the `image` field. |
| GET/PATCH/DELETE | `templates/{id}/` | Admin | Inspect or update a template. In-use templates are preserved. |
| GET | `generate/csv-template/` | Admin | Download the expected recipient CSV. |
| POST | `generate/validate-csv/` | Admin | Validate uploaded recipient data. |
| POST | `generate/bulk/` | Admin | Issue certificates from validated recipient rows. |
| POST | `generate/single/` | Admin | Issue one certificate. |
| POST | `generate/preview/` | Admin | Render a template preview. |
| GET | `generate/batches/`, `generate/batches/{id}/` | Admin | List or inspect generation batches. |
| POST | `{id}/pdf/` | Owner/admin | Upload or replace the stored PDF, subject to validation. |
| GET | `{id}/pdf/download/`, `{id}/image/` | Owner/admin or public preview policy | Download or display stored certificate media. |
| POST | `{id}/retry-email/` | Admin | Retry certificate email delivery. |

## Other APIs

- `GET /api/dashboard/`: role-scoped dashboard metrics and recent records.
- `/api/verification/check/` and `/api/verification/history/`: verification lookup and authenticated history.
- `/api/notifications/`, `unread-count/`, `read-all/`, and `{id}/read/`: in-app notification operations.
- `GET /api/audit/`: administrator audit log listing.

Use the route declarations and serializers as the authoritative source when
adding fields; this document intentionally does not promise cryptographic
file authenticity, QR scanning, or immutable audit storage.
