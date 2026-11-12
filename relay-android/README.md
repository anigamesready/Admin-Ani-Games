# Ani WoL Relay Android

Standalone Android companion app for the Ani Games Ready Admin WoL relay integration. This standby build uses application ID \`com.anigames.aniwolrelay.standby\`, separate from the original legacy Relay application.

## Network recovery

The app first uses the Android/Wi-Fi DNS resolver. If the router or Wi-Fi DNS cannot resolve the Supabase hostname, the app automatically falls back to DNS-over-HTTPS through Cloudflare and then Google. Both paths use HTTPS certificate and hostname validation; no Android Private DNS setting or manual network configuration is required. DNS answers are cached to avoid unnecessary lookups.

The same resolver is used for pairing, heartbeat, polling, command acknowledgements, and Admin probe acknowledgements. A 45-second authenticated heartbeat refreshes the server's 90-second ONLINE window; every Admin direct probe is explicitly acknowledged by the app. The configured Supabase project remains DB1 (\`wzkjpycjizexxcxrfdvr\`); this patch does not switch DB targets or alter database pairing rows.

## Standby behavior

The app uses a foreground service with persistent notification, partial CPU wake lock while Relay is enabled, Wi-Fi lock, encrypted relay-token storage, local UDP Magic Packet broadcast, battery/temperature telemetry, boot recovery, and HTTPS command polling. The activity may be sent to Home and the screen may be locked while the service remains enabled.

Android and MIUI can still restrict autostart/background execution through protected system controls; a normal app cannot silently override those controls. Force Stop, manually disabling the service, powering off the phone, or an OEM/system kill can still stop a relay. Keep the phone ventilated and use a good-quality charger.

Polling updates the backend last-seen status and receives queued WoL commands. It must remain enabled unless replaced with push delivery. DB1/DB2 relay enrollment/device/command rows are not synchronized automatically; do not switch DB targets expecting a paired relay to survive.

## Compatibility note

The previous 1.0.2 debug APK was signed by an ephemeral GitHub Actions debug key. A new debug APK cannot be guaranteed to update it in place. If Android rejects this update as a signature mismatch, the old app must be uninstalled before installing this build, and the Relay must be paired once more. Do not remove the old app until this APK is ready.
