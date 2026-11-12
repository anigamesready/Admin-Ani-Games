# Ani WoL Relay Android

Standalone Android companion app for the Ani Games Ready Admin WoL relay integration. This standby build uses application ID \`com.anigames.aniwolrelay.standby\`, separate from the original legacy Relay application.

## Network recovery

The app first uses the Android/Wi-Fi DNS resolver. If the router or Wi-Fi DNS cannot resolve the Supabase hostname, the app automatically falls back to DNS-over-HTTPS through Cloudflare and then Google. Both paths use HTTPS certificate and hostname validation; no Android Private DNS setting or manual network configuration is required. DNS answers are cached to avoid unnecessary lookups.

The same resolver is used for pairing, heartbeat, polling, command acknowledgements, and Admin probe acknowledgements. A 45-second authenticated heartbeat refreshes the server's 90-second ONLINE window; every Admin direct probe is explicitly acknowledged by the app. The configured Supabase project remains DB1 (\`wzkjpycjizexxcxrfdvr\`); this patch does not switch DB targets or alter database pairing rows.

## Standby behavior

The app uses a foreground service with persistent notification, partial CPU wake lock while Relay is enabled, Wi-Fi lock, encrypted relay-token storage, local UDP Magic Packet broadcast, battery/temperature telemetry, boot recovery, and HTTPS command polling. The activity may be sent to Home and the screen may be locked while the service remains enabled.

Android and MIUI can still restrict autostart/background execution through protected system controls; a normal app cannot silently override those controls. Force Stop, manually disabling the service, powering off the phone, or an OEM/system kill can still stop a relay. Keep the phone ventilated and use a good-quality charger.

Heartbeat and probe acknowledgement update the backend last-seen status; polling receives queued WoL commands and direct probes. Polling must remain enabled unless replaced with push delivery. DB1/DB2 relay enrollment/device/command rows are not synchronized automatically; do not switch DB targets expecting a paired relay to survive.

## Compatibility note

The 1.0.3 and 1.0.4 CI debug APKs have different signing certificates (verified SHA-256 fingerprints differ), so Android will reject 1.0.4 as an in-place update. Uninstall only the old Ani WoL Relay Standby app from the Redmi 6 Pro, install 1.0.4, and pair once with a fresh Admin code. The server migration preserves the primary Redmi slot when a stale primary is re-paired by a device with the same model. Do not uninstall Relay apps on other phones.
