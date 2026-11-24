import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
const page = readFileSync('android/app/src/main/assets/web/admin.html', 'utf8');
const gradle = readFileSync('android/app/build.gradle', 'utf8');
const manifest = readFileSync('android/app/src/main/AndroidManifest.xml', 'utf8');

test('Admin has distinct PC target and Android router selectors', () => {
  assert.equal((page.match(/id="wakeRelayTarget"/g) || []).length, 1);
  assert.equal((page.match(/id="wakeRelayAndroidSelect"/g) || []).length, 1);
  assert.match(page, /function selectedAndroidRelay\(\)/);
  assert.match(page, /function renderWakeRelayAndroidOptions\(/);
  assert.match(page, /ani_games_admin_wol_selected_relay_v1/);
});
test('Selected relay gets its own probe and only that relay gets the WoL command', () => {
  assert.match(page, /wol_relay_probe_request_selected/);
  assert.match(page, /wol_relay_enqueue_selected/);
  assert.match(page, /p_target_device_id:target\.id/);
  assert.match(page, /p_relay_id:relayId/);
  assert.match(page, /SERVER_RELAY_SELECTION_MISMATCH/);
  assert.match(page, /RELAY_RPC_NAMES=new Set\(\[[^\]]*wol_relay_enqueue_selected/);
  assert.match(page, /RELAY_RPC_NAMES=new Set\(\[[^\]]*wol_relay_probe_request_selected/);
});
test('Both legacy send handlers retain the Owner guard and use the explicit route', () => {
  const handlers = [...page.matchAll(/async function requestWakePc2\(\)\s*\{[\s\S]*?^\}/gm)].map(m => m[0]);
  assert.ok(handlers.length >= 2);
  for (const fn of handlers) {
    assert.match(fn, /isWakeRelayOwner\(\)/);
    assert.match(fn, /wol_relay_enqueue_selected/);
    assert.doesNotMatch(fn, /rpc\('wol_relay_enqueue',/);
  }
  assert.match(page, /function isWakeRelayOwner\(\)/);
});
test('Offline/stale relays are disabled and freshness is bounded to 90 seconds', () => {
  assert.match(page, /const disabled = relayHeartbeatFresh\(r\) \? '' : ' disabled'/);
  assert.match(page, /age <= 90000/);
  assert.match(page, /RELAY OFFLINE/);
  assert.doesNotMatch(page, /Promise\.all\([^)]*wol_relay_enqueue_selected/);
});
test('V12.1.57 keeps a separate SAFE TEST install identity', () => {
  assert.match(gradle, /versionCode 84/);
  assert.match(gradle, /versionName '12\.1\.57'/);
  assert.match(gradle, /applicationId 'com\.anigames\.billingadmin\.v157dbtest'/);
  assert.doesNotMatch(gradle, /applicationId 'com\.anigames\.billingadmin\.v156dbtest'/);
  assert.match(manifest, /AniGames Admin DB Android V12\.1\.57 MULTI-SITE WoL SAFE TEST/);
  assert.match(page, /V12\.1\.57-MULTI-SITE-WOL-ROUTING/);
});
test('Previous Admin core remains connected', () => {
  for (const token of ['admin_create_rental_global','admin_update_rental_global','admin_delete_rental_global',
    'report_detailed_usage_page','report_summary_compact','admin_remote_play_dashboard',
    'admin_get_billing_stop_pause_policy','admin_set_billing_stop_pause_policy',
    'wol_relay_command_status','startLocalAdmin();','127.0.0.1:8787'])
    assert.ok(page.includes(token), 'missing regression marker: ' + token);
  assert.doesNotMatch(page, /startDualDbAdmin\(\);/);
});
