# Ani WoL Relay Android

Standalone Android companion app for the Ani Games Ready Admin V12.1.47 Android WoL relay integration.

Target hardware: Redmi 6 Pro (primary). The app is minSdk 23, uses a foreground service, encrypted relay-token storage, local UDP Magic Packet broadcast, battery/temperature telemetry, boot recovery, and HTTPS polling through the DB1 ani-games-api gateway.

This is a separate relay identity; it is never registered as a PC Billing device. Charge control is intentionally read-only unless the handset's charging hardware exposes a supported safe control interface.
