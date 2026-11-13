# Admin APK — DB Android Track Audit

## Branch identity
- Work branch: `admin-v12.1.46-DB-Android`
- Source repository: `anigamesready/Admin-Ani-Games`
- Source baseline branch: `feature/admin-v12.1.46-monthly-yearly-member-rankings`
- Source baseline commit: `26f1571f6a31ac3eaea3fc8a698fea1d157d08f3`
- This DB Android branch was created from that exact commit and verified identical before this audit document was added.
- Baseline Admin APK version: V12.1.46 (the checked build workflow validates versionCode 74 and versionName 12.1.46).

## Source/build audit
The Admin build workflow `.github/workflows/build-android-apk.yml` extracts `AniGames-Admin-V12.1.4-ANDROID-PASSWORD-RESET-PATCH-v3.zip` and applies a long, ordered patch chain. The chain includes dual-DB preflight/routing, DB sync, gateway readiness, owner authorization, PC recovery, alerts, global rental management, Windows command acknowledgement, export/reporting and V12.1.46 monthly/yearly report changes.

The inherited workflow is explicitly a Supabase/dual-DB build pipeline. It is intentionally not added to the DB Android branch's push-trigger list; do not invoke it as proof of a local PostgreSQL-compatible APK.

## Backend/RPC dependencies identified from the patch chain
At minimum, the local backend adapter must account for these existing behaviors:
- Admin authentication/context and owner/admin role enforcement (`admin_context`);
- PC list/status, pairing recovery (`create_device_recovery_enrollment`), notifications (`admin_recent_alerts`);
- global rental list/create/update/delete and status management (`admin_rental_accounts_global`, `admin_create_rental_global`, `admin_update_rental_global`, `admin_disable_rental_global`, `admin_delete_rental_global`);
- PC session inspection and command dispatch/acknowledgement (`admin_selected_sessions`, `admin_command`, `billing_command`);
- monthly/yearly report breakdown (`report_rental_period_breakdown`) and report export support;
- the legacy `db-core-sync` Edge Function path must be evaluated, not assumed compatible with the Redmi API.

## DB Android separation rules
1. Keep this branch separate from `main`, the existing dual-DB Supabase branches, and production configuration.
2. Do not include a client-side selector that changes DB1/DB2 as part of the Redmi DB Android path.
3. Implement server-side owner/admin/reseller authorization; never trust organization IDs or role labels supplied by the client.
4. Preserve existing rental CRUD, PC control acknowledgement, reports, pairing recovery and notification behavior.
5. Keep Windows controls separate from database service controls. Database ON/OFF must never stop or alter the Blynk/WoL relay.
6. Never embed PostgreSQL passwords or service credentials in the APK.

## Current status
This commit only records the audit. No runtime source, Supabase project, route-control row or production configuration was changed. The existing Admin build pipeline remains Supabase-dependent; the Redmi API is not yet a drop-in replacement for Admin authentication, RPC, reports or device commands.

## Required regression gate before a DB Android APK
- Validate login/session refresh and role gates for owner/admin.
- Test rental create/edit/disable/delete while a billing session is active.
- Test PC list, heartbeat freshness, pairing recovery and command lifecycle including positive/negative acknowledgement.
- Verify monthly/yearly reporting, per-PC breakdown and Excel/PDF export.
- Verify Android layout does not clip dashboard/report screens.
- Test the APK against staging data only before considering any production switch.
