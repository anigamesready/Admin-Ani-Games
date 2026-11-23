# Admin Remote Play Pairing Console

Status: implementation requirements for V12.1.54 branch. V12.1.53 already contains the first Owner-only Remote Play permission and one-time credential menu; the currently installed V12.1.49 APK does not contain that menu.

## Required Owner-only navigation

Use a clearly named menu **Pairing Remote Play** (or **Remote Play**) adjacent to PC Aktif. Only the Master/Owner role may see or open it. Enforce the role again on every action and on the API; hiding a menu is not authorization.

## Required screens

1. **Host PC**
   - PC name / client ID, online state, Host Agent enrollment, Sunshine readiness, relay tunnel status and last heartbeat.
   - Allow / revoke Remote Play Host permission.
   - Issue a one-time Host Agent enrollment code, 64 hex characters, 15-minute expiry; show once only.
   - Revoke Host tunnel or re-enroll with an explicit confirmation.

2. **Rental permission**
   - Rental ID, active/expired/disabled state, remaining balance, expiry, Remote Play permission.
   - Allow / revoke permission.
   - Issue a one-time customer activation credential; show once only and state that it must be delivered privately.
   - Re-issue must revoke previous activation/session credentials according to backend contract.

3. **Client installations and PC pairings**
   - Customer install name/ID, rental owner, platform, paired PC list, created/last-seen time and revoked state.
   - Revoke a lost phone installation.
   - Revoke one pairing for a selected PC without disabling the rental account.
   - Do not display personal Cloudflare organization email to renters; Cloudflare Mesh remains owner/operator infrastructure only.

4. **Active sessions and media route**
   - Rental, Host PC, session state, remaining time/deadline, connection route (direct/relay), relay health and last heartbeat.
   - Admin Stop / revoke with server-side settlement.
   - Show a clear blocker when relay or Host tunnel is not ready; never represent an unverified route as ready.

## Compatibility guardrails

- Preserve all existing Admin tabs and actions: Dashboard, PC Aktif, Pairing PC, Laporan, Rental, StarDesk, Reseller, User Billing Control, Windows Chat, FREE TEST, PAUSE/STOP BILLING and WoL.
- Do not change DB quick settings, selected DB, saved API base URL, gateway, route policy, port selection, or local API configuration.
- Do not add a new DB connection flow. Call the same API adapter the currently working Admin app uses.
- Do not blindly publish a new packageId. Confirm the currently installed package/applicationId and signing compatibility, or provide an explicit migration/import path for the saved DB gateway setting and authenticated state. A side-by-side package starts with its own WebView localStorage and must not be assumed to inherit the working gateway URL.
- V12.1.53 package com.anigames.billingadmin.v153db is a separate package. The SAFE-TEST package is com.anigames.billingadmin.v153dbtest. Do not ask the user to replace their working Admin app with either without validating saved API settings and auth continuity.
- Preserve the existing independent Blynk/WoL sidecar and all non-Remote-Play behavior.
