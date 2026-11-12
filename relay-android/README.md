# Ani WoL Relay Android

Standalone Android companion app for the Ani Games Ready Admin V12.1.50 Android WoL relay integration.

Target hardware: Redmi 6 Pro (primary). The app is minSdk 23 and runs a user-visible Android foreground service with a persistent notification, a partial CPU wake lock while Relay is enabled, a Wi-Fi lock, encrypted relay-token storage, local UDP Magic Packet broadcast, battery/temperature telemetry, boot recovery, and HTTPS command polling through the DB1 ani-games-api gateway.

## One-time Redmi / MIUI standby setup

1. Pair from Admin, then press **Aktifkan Mode Siaga 24 Jam** in Relay.
2. Allow the Android battery-optimization exemption prompt.
3. In Xiaomi Autostart settings, enable Ani WoL Relay.
4. In Xiaomi app battery settings, select No restrictions / Tanpa Batasan for Ani WoL Relay.
5. Keep the permanent Relay notification visible. The activity may be sent to Home and the screen may be locked.

The app can open the Android and MIUI settings screens directly, but Android does not allow a normal app to silently change protected system switches. The user must confirm the displayed settings. Force Stop, manually disabling the service, powering off the phone, or an OEM/system kill can still stop a relay. The long-lived CPU wake lock is intentional for the always-on gateway use case and can increase power consumption and temperature; use a good charger and ventilation.

## Network and status behavior

The Relay polls the gateway for queued WoL commands. The current DB function updates `last_seen_at` during `wol_relay_poll`, so polling also refreshes the Admin's ONLINE status. The separate telemetry heartbeat remains for battery/temperature metadata. Do not remove polling without replacing it with a push-delivery path (for example, FCM), otherwise queued WoL commands cannot reach the phone while idle.

This is a separate relay identity; it is never registered as a PC Billing device. Charge control is intentionally read-only unless the handset's charging hardware exposes a supported safe control interface.

## DB1/DB2 failover note

The relay schema and API are deployed on both databases, but relay enrollment/device/command rows currently live only in the active database. The live route still reports backup_ready=false and sync_ready=false. Do not switch DB targets expecting a paired relay to survive until relay rows are included in the approved DB sync/replication process.
