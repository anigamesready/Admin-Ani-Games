# Reseller APK — DB Android Track Audit

## Branch identity
- Work branch: `reseller-v1.0.6-DB-Android`
- Source repository: `anigamesready/Admin-Ani-Games`
- Source baseline branch: `release/reseller-v1.0.6-remember-login-rental-status`
- Source baseline commit: `a67c2f6318230671a7d7776bf6040c39bca6ff97`
- This DB Android branch was created from that exact commit and verified identical before this audit document was added.
- Baseline Reseller APK version: V1.0.6; the build workflow validates versionCode 136 and versionName 1.0.6.

## Source/build audit
The Reseller build workflow `.github/workflows/build-reseller-apk.yml` extracts `Ani-Games-Reseller-Android-SOURCE-v11.30.0.zip`, verifies the Android project and the supplied HTML Review template archive using fixed SHA-256/size checks, then applies:
- global DB route checks for both Supabase projects;
- global rental CRUD without requiring a selected/online PC;
- hard delete with active-session safeguards;
- remembered login and editable ACTIVE / DISABLE / EXPIRED rental status.

The current pipeline is still bound to Supabase DB1/DB2. Its automatic push filters list the original release/feature branches, not this DB Android branch. Do not use that inherited pipeline as a local PostgreSQL build.

## Backend and security dependencies
- Login currently calls the Supabase billing login/context RPCs and relies on the global DB route check.
- Rental operations use `billing_reseller_rental_accounts_global`, `billing_reseller_create_rental_global`, `billing_reseller_edit_rental_global` and `billing_reseller_delete_rental_global`.
- The UI blocks PC/Windows pairing and control commands by design; keep that restriction.
- The remembered-login patch stores both username and password in WebView `localStorage`. This is a security concern to address in the DB Android branch. Prefer a short-lived/revocable session token stored through Android Keystore-backed storage; do not carry forward plaintext password persistence without a deliberate security review.

## DB Android separation rules
1. Keep this branch independent from the Admin DB Android branch and all Supabase dual-DB/production branches.
2. Reseller users must only access their own rental records; do not grant direct SQL/database access or Admin/Owner permissions.
3. Enforce reseller identity and organization scope on the Redmi server; do not accept role or org scope from an untrusted client payload.
4. Preserve create/edit/delete, ACTIVE / DISABLE / EXPIRED status and active-session delete safeguards.
5. Keep reseller UI free of PC pairing, Windows command, shutdown, WoL and relay controls.
6. Never embed database passwords or server-side service secrets in the APK.

## Current status
This commit only records the audit. No runtime source, Supabase project, route-control row or production configuration was changed. The Redmi API currently provides only the local health endpoint; reseller authentication and rental RPC equivalents have not yet been implemented.

## Required regression gate before a DB Android Reseller APK
- Test successful/failed login, session expiry and safe remembered sign-in.
- Verify reseller A cannot read or mutate reseller B's rental records.
- Test create/edit/delete and ACTIVE / DISABLE / EXPIRED transitions.
- Confirm an active rental/session cannot be deleted in violation of existing safeguards.
- Confirm forbidden Windows/pairing controls remain absent from reseller UI.
- Test on a fresh install before deploying to reseller devices.
