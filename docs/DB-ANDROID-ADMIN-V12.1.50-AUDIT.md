# Admin APK DB Android Track — V12.1.50 Baseline Audit

## Verified source identity
- Repository: `anigamesready/Admin-Ani-Games`
- Isolated work branch: `admin-v12.1.50-DB-Android`
- Baseline branch: `fix/ani-wol-master-pairing-guard-20261112`
- Baseline commit: `9460e8dcbdbf69706408dd0507016cf0037ff153`
- App build identity asserted by the workflow: versionName `12.1.50`, versionCode `78`, applicationId `com.anigames.billingadmin.v150`.
- Source ZIP: `AniGames-Admin-V12.1.4-ANDROID-PASSWORD-RESET-PATCH-v3.zip`.
- The V12.1.50 workflow applies the Admin V12.1.47, V12.1.48, V12.1.49 and V12.1.50 patches on top of the earlier Admin feature chain.
- New DB Android branch is not included in the inherited automatic push branch filter. This prevents the old Supabase/dual-DB pipeline from running automatically on DB Android changes.

## Why this replaces the V12.1.46 working baseline
V12.1.46 remains a valid earlier Admin source and is preserved in the older `admin-v12.1.46-DB-Android` branch. The current audited Admin source branch extends it by 74 commits and contains:
- the existing Admin V12.1.46 reporting and rental behavior;
- Android WoL relay UI and role restrictions;
- relay reliability and master/owner role guards;
- manual relay probe support and its database reference patch.

This does **not** mean the relay app is being modified by the DB Android project. Relay remains a separate runtime and service.

## Existing Supabase integration surface to replace
The V12.1.50 Admin app build still applies Supabase-oriented patch chains. The local DB adapter must preserve these behaviors while removing DB1/DB2 route switching from the DB Android path:
- Admin login and context, role/org authorization, session refresh and owner-only actions;
- PC listing, device heartbeat state and PC recovery enrollment;
- global rental list, create, update, disable and delete;
- PC command dispatch and command acknowledgement/status;
- daily, monthly, yearly, per-PC and member ranking reports plus file exports;
- Admin alerts and notification feed;
- manual WoL status/probe remains a separate relay integration. DB service start/stop must never operate the relay.

Important RPC names found in the existing app patches include:
`admin_context`, `admin_context_v2`, `admin_recent_alerts`, `create_device_recovery_enrollment`,
`admin_rental_accounts_global`, `admin_create_rental_global`, `admin_update_rental_global`,
`admin_disable_rental_global`, `admin_delete_rental_global`, `admin_selected_sessions`,
`admin_command`, `billing_command`, `billing_command_status`, and `report_rental_period_breakdown`.

## Auth and authorization requirements
- Current Admin login resolves a username/email to an Auth email and then uses Supabase Auth; Admin context is tied to the authenticated user ID and the Admin account/org tables.
- The Redmi implementation must provide a new local session/token system. It must not trust a client-supplied role, user ID or org ID.
- Owner and reseller-admin access must be derived server-side from the authenticated account.
- Reseller access must stay scoped to the reseller's own organization.
- No service-role or database credentials may be embedded in the APK.

## Current status
This commit records the correct latest Admin baseline and the DB Android compatibility requirements. No production Supabase code, DB route, relay process or existing release branch was changed. No APK build has been triggered from this DB Android branch.

## Required regression gate
- Login, logout, expired/revoked session and role/org access.
- Rental add/edit/disable/delete, including during an active PC session.
- Active/paused session and offline lease delete protections.
- PC list, pairing recovery, command queue and explicit completed/failed acknowledgement.
- Daily/monthly/yearly/per-PC reports, ranking periods and Excel/PDF exports.
- Notification dedupe and safe Android rendering.
- No DB Android service control action may stop or modify the separate Blynk/WoL relay.
