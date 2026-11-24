import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const gateway = 'https://ani-games-db-android-stage-ws-relay.anigamesready.workers.dev';
const pages = {
  admin: readFileSync('android/app/src/main/assets/web/admin.html', 'utf8'),
  login: readFileSync('android/app/src/main/assets/web/index.html', 'utf8'),
  control: readFileSync('android/app/src/main/assets/web/admin-control.html', 'utf8'),
};
const gradle = readFileSync('android/app/build.gradle', 'utf8');
const manifest = readFileSync('android/app/src/main/AndroidManifest.xml', 'utf8');
const page = pages.admin;

test('All login/admin/control endpoints default to the HTTPS Redmi gateway', () => {
  for (const [name, source] of Object.entries(pages)) {
    assert.ok(source.includes(gateway), name + ' does not contain the gateway default');
    assert.ok(source.includes('ANI-ADMIN-V12.1.57-ONLINE-GATEWAY-DEFAULT'), name + ' lacks gateway marker');
    assert.doesNotMatch(source, /http:\/\/127\.0\.0\.1:878[78]/, name + ' still has loopback default');
    assert.doesNotMatch(source, /DB Android Lokal|Alamat API Lokal/, name + ' still displays local mode');
  }
  assert.match(pages.login, /ALAMAT GATEWAY DB ANDROID/i);
  assert.match(pages.control, /function localApiBase\(\)/);
  assert.match(page, /DB Android Online/);
});

test('Gateway routing preserves the V12.1.53 DB Android RPC adapter', () => {
  assert.match(page, /function localApiBase\(\)/);
  assert.match(page, /async function localJson\(/);
  assert.match(page, /fetch\(localApiBase\(\)\+path/);
  assert.match(page, /localApiBase\(\)\+'\/rest\/v1\/rpc\//);
  assert.match(page, /startLocalAdmin\(\);/);
  assert.doesNotMatch(page, /startDualDbAdmin\(\);/);
});

test('Stop/Pause, Free Test and Remote Play access use canonical Master/Owner role aliases', () => {
  for (const id of [
    'billingStopPausePolicyNav',
    'billingStopPausePolicyCard',
    'billingStopPausePolicySwitch',
    'billingStopPausePolicySave',
  ]) assert.equal((page.match(new RegExp('id="' + id + '"', 'g')) || []).length, 1);

  assert.match(page, /function billingStopPausePolicyIsOwner\(\)\{[^}]*isWakeRelayOwner\(\)===true/);
  assert.match(page, /function freeTestPolicyIsOwner\(\)\{[^}]*isWakeRelayOwner\(\)===true/);
  assert.match(page, /function isRemotePlayOwner\(\)\{[^}]*isWakeRelayOwner\(\)===true/);

  const visibility = page.match(/function applyPairingRoleUI\(\)\{[\s\S]*?\n\}/)?.[0] || '';
  assert.match(visibility, /freeTestNav\.classList\.toggle\('hidden',!owner\)/);
  assert.match(visibility, /stopPauseNav\.classList\.toggle\('hidden',!owner\)/);
  assert.match(visibility, /pairingNav/);

  const openFn = page.match(/function openBillingStopPausePolicyMenu\(\)\{[\s\S]*?\n\}/)?.[0] || '';
  const loadFn = page.match(/async function loadBillingStopPausePolicy\(\)\{[\s\S]*?\n\}/)?.[0] || '';
  assert.match(openFn, /if\(!billingStopPausePolicyIsOwner\(\)\)/);
  assert.match(loadFn, /if\(!billingStopPausePolicyIsOwner\(\)\)/);
});

test('Policy RPCs remain on the Admin gateway, not the Blynk/WoL relay allowlist', () => {
  const relayAllow = page.match(/const RELAY_RPC_NAMES=new Set\(\[([^\]]*)\]\);/)?.[1] || '';
  assert.doesNotMatch(relayAllow, /admin_get_billing_stop_pause_policy|admin_set_billing_stop_pause_policy/);
  assert.match(page, /admin_get_billing_stop_pause_policy/);
  assert.match(page, /admin_set_billing_stop_pause_policy/);
  assert.match(page, /wol_relay_probe_request/);
  assert.match(page, /SB_FUNCTION_URL\+'\/iot\/status'/);
});

test('V12.1.53 core features remain and the APK is side-by-side SAFE TEST', () => {
  for (const token of [
    'V12.1.53-REMOTE-PLAY-SHARED-DB-PORT-8787',
    'V12.1.51-BILLING-STOP-PAUSE-POLICY',
    'admin_remote_play_dashboard',
    'admin_remote_play_set_host_permission',
    'admin_remote_play_set_rental_permission',
    'admin_remote_play_issue_client_credential',
    'admin_remote_play_issue_host_enrollment',
    'admin_rental_accounts_global',
    'admin_create_rental_global',
    'admin_update_rental_global',
    'admin_delete_rental_global',
    'report_detailed_usage_page',
    'report_summary_compact',
    'wol_relay_probe_request',
    'V12.1.57-STOP-PAUSE-OWNER-ROLE-VISIBILITY',
  ]) assert.ok(page.includes(token), 'missing retained feature: ' + token);

  assert.match(gradle, /applicationId 'com\.anigames\.billingadmin\.v157online'/);
  assert.doesNotMatch(gradle, /applicationId 'com\.anigames\.billingadmin\.v153db'/);
  assert.match(gradle, /versionCode 84/);
  assert.match(gradle, /versionName '12\.1\.57'/);
  assert.match(manifest, /android:label="AniGames Admin Online V12\.1\.57 SAFE TEST"/);
});
