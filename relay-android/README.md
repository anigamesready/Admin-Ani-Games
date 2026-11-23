# Ani WoL Relay Android

Standalone Android companion app for the Ani Games Ready Admin V12.1.50 Android WoL relay integration.

V1.0.2 uses package `com.anigames.aniwolrelay.v102` so it installs beside the earlier V1.0.1 build even when the debug signing certificate changes. Pair the new installation once; keep the earlier app until the new relay has passed a live Admin probe.

Target hardware: Redmi 6 Pro (primary). The app is minSdk 23, uses a foreground service, encrypted relay-token storage, local UDP Magic Packet broadcast, battery/temperature telemetry, boot recovery, and HTTPS polling through the DB1 ani-games-api gateway.

This is a separate relay identity; it is never registered as a PC Billing device. Charge control is intentionally read-only unless the handset's charging hardware exposes a supported safe control interface.

## DB1/DB2 failover note
The relay schema and API are deployed on both databases, but relay enrollment/device/command rows currently live only in the active database. The live route still reports backup_ready=false and sync_ready=false. Do not switch DB targets expecting a paired relay to survive until relay rows are included in the approved DB sync/replication process.
