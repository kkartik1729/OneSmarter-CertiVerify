# Database schema overview

The Django ORM defines the schema and migrations are the source of truth. The
project uses the configured PostgreSQL database in normal deployments. Local
SQLite is optional for lightweight development; no manual SQL schema edits are
required. This guide describes the relationships and important data groups,
not a substitute for migration files.

## Accounts

- Django's configured user model stores username, email, password hash, staff,
  superuser, and active state.
- `UserProfile` is one-to-one with a user and stores role, contact fields,
  email-verification state, MFA state/secrets, and Google subject.
- `EmailVerificationToken`, `PasswordResetToken`, `PasswordResetRequest`, and
  `MFARecoveryToken` belong to a user and store hashed single-use credentials,
  expiry, and consumption state. Raw OTPs/tokens are not stored.

## Certificates

- `Course` and `CertificateTemplate` are administrator-managed issuance data.
- `GenerationBatch` records bulk issuance inputs, status, counts, and errors;
  each resulting `Certificate` may reference its batch and template/course.
- `Certificate` stores a unique certificate number, recipient, issue/status
  information, ownership, layout-related metadata, and its generated media
  reference. Ownership is nullable for certificates awaiting a matching
  recipient account.
- `CertificatePDF` stores validated PDF bytes associated with a certificate.

## Verification, audit, and notifications

- `VerificationAttempt` records a lookup result and optional requester and
  matched certificate. Public lookup does not expose internal attempt IDs.
- `AuditLog` records administrative and security-relevant actions, actor,
  target, timestamp, and structured metadata.
- `Notification` belongs to a recipient and may reference a certificate; read
  state and creation time support dashboard retrieval.

## Data safety

Do not drop, truncate, flush, or recreate existing tables to resolve an
application issue. Inspect `python manage.py showmigrations` and review
`python manage.py migrate --plan` before applying a schema change. Existing
certificate records and media references must be preserved during migration.
