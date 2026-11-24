# Multi-Site WoL Routing V1

## Admin behavior
The Admin selects two independent objects: a paired PC target and an Android WoL relay/router. The selected relay is saved locally on the Admin device. The relay list shows the registered relay name/model, heartbeat state, and battery level.

Before WoL, Admin sends a direct probe to that exact relay. A heartbeat older than 90 seconds is shown as OFFLINE and cannot be used. A failed direct probe blocks enqueue. The selected relay ID is sent with the PC target ID to `api.wol_relay_enqueue_selected`.

## Server behavior
- `api.wol_relay_enqueue_selected(target_id, relay_id)` checks Master/Super Admin, organization access, target status, target LAN MAC, selected relay organization, non-revoked status, and heartbeat freshness.
- The command row is inserted with only the selected `relay_id`; the relay polling contract remains unchanged.
- No auto-fallback to a different site and no command fan-out to every registered relay.
- Legacy `wol_relay_enqueue(target_id)` and `wol_relay_probe_request()` remain unchanged for older clients.
- The DB1 sidecar remains separate from the DB Android local Admin API. DB2 and the billing PC app are not changed.

## Important LAN constraint
The operator must select the Android relay physically connected to the same LAN/broadcast domain as the target PC. The current device metadata does not automatically identify the two physical site networks. This release gives explicit deterministic selection; automatic site mapping is a later enhancement once each PC and relay has a trusted site/network assignment.
