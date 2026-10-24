# Security incident response: repository dump and secret rotation

## Immediate application changes

`backend/certiverify_backup.dump` has been removed from the working tree. Root and backend ignore rules now exclude `.dump`, `.sql`, `.backup`, and `.bak` files. Removing the working copy does not erase copies already present in Git history, clones, CI artifacts, or deployment backups.

## Required authorized actions

1. Treat all credentials and personal data in the dump and all credentials ever committed in this repository as compromised. Rotate the administrator password and TOTP enrollment, Django `DJANGO_SECRET_KEY`, database credentials, SMTP credentials, and any other credentials confirmed in the dump/history. Do not reuse prior values.
2. Deploy new secrets through the production secret manager/environment. The application now fails during startup if `DJANGO_SECRET_KEY` is blank or a known placeholder. `SIMPLE_JWT` does not override `SIGNING_KEY`, so SimpleJWT and custom MFA challenge tokens use Django's `SECRET_KEY`. Rotating it invalidates tokens signed with that key. Also invalidate server-side Django sessions and any separately signed tokens if deployment overrides the JWT signing key.
3. Coordinate with repository collaborators and CI/deployment owners before rewriting shared history. After authorization, install `git-filter-repo`, make a verified mirror backup, then from a mirror clone run:

   ```sh
   git filter-repo --path backend/certiverify_backup.dump --invert-paths
   git log --all --oneline -- backend/certiverify_backup.dump
   ```

   Review all refs and tags and scan history for secrets without printing matching values. Coordinate the rewritten refs with collaborators, invalidate old clones, and only then force-push using the repository's approved procedure. Do not run this against the shared remote without explicit approval.
4. Remove old dump copies from CI artifacts, deployment bundles, object storage, developer clones, and backups under the organization's retention/security procedure. Preserve required audit/business records in their authoritative database; do not restore from or distribute the leaked dump.
5. Configure a shared Django database cache in production. The current production cache backend is Django `DatabaseCache`; provision its table before starting application workers:

   ```sh
   python manage.py createcachetable certiverify_cache
   ```

   The command is safe to rerun when the table already exists only if the Django version reports it as existing; verify the table before retrying.

## Verification

Check that sensitive files are ignored with `git check-ignore -v backend/certiverify_backup.dump backend/.env path/to/backup.sql`, that no backup is included in frontend build output, and that history no longer contains the dump after the coordinated rewrite. Never include raw secret values in tickets, command output, or logs.
