import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const page = readFileSync('android/app/src/main/assets/web/admin.html', 'utf8');
const gradle = readFileSync('android/app/build.gradle', 'utf8');
const manifest = readFileSync('android/app/src/main/AndroidManifest.xml', 'utf8');
const index = readFileSync('android/app/src/main/assets/web/index.html', 'utf8');
const control = readFileSync('android/app/src/main/assets/web/admin-control.html', 'utf8');

const policyOwnerFn = page.match(/function billingStopPausePolicyIsOwner\(\)\{[^}]*\}/)?.[0] || '';
const visibilityBlock = page.match(/const stopPauseOwner=billingStopPausePolicyIsOwner\(\);[\s\S]{0,260}?stopPauseCard\.classList\.toggle\('hidden',!stopPauseOwner\);/)?.[0] || '';
const openFn = page.match(/function openBillingStopPausePolicyMenu\(\)\{[\s\S]*?\n\}/)?.[0] || '';
const loadFn = page.match(/async function loadBillingStopPausePolicy\(\)\{[\s\S]*?\n\}/)?.[0] || '';
const saveFn = page.match(/async function saveBillingStopPausePolicy\(\)\{[\s\S]*?\n\}/)?.[0] || '';
const relayAllow = page.match(/const RELAY_RPC_NAMES=new Set\(\[([^\]]*)\]\);/)?.[1] || '';

test('Stop/Pause menu is present exactly once and uses canonical Master/Owner role aliases', () => {
  assert.equal((page.match(/id="billingStopPausePolicyNav"/g) || []).length, 1);
  assert.equal((page.match(/id="billingStopPausePolicyCard"/g) || []).length, 1);
  assert.equal((page.match(/id="billingStopPausePolicySwitch"/g) || []).length, 1);
  assert.equal((page.match(/id="billingStopPausePolicySave"/g) || []).length, 1);
  assert.match(policyOwnerFn, /isWakeRelayOwner\(\)===true/);
  assert.match(page, /function isWakeRelayOwner\(\)[\s\S]*?master_owner[\s\S]*?master_admin/);
  assert.match(visibilityBlock, /const stopPauseOwner=billingStopPausePolicyIsOwner\(\)/);
  assert.match(visibilityBlock, /!stopPauseOwner/);
});

test('Menu opening, reading and saving are restricted to Master/Owner', () => {
  assert.match(openFn, /if\(!billingStopPausePolicyIsOwner\(\)\)/);
  assert.match(loadFn, /if\(!billingStopPausePolicyIsOwner\(\)\)/);
  assert.match(saveFn, /if\(!billingStopPausePolicyIsOwner\(\)\)/);
  assert.match(saveFn, /admin_set_billing_stop_pause_policy/);
  assert.match(loadFn, /admin_get_billing_stop_pause_policy/);
  assert.match(saveFn, /await loadBillingStopPausePolicy\(\)/);
});

test('Policy RPCs use the local DB Android API, not the Blynk/WoL Supabase sidecar', () => {
  assert.doesNotMatch(relayAllow, /admin_get_billing_stop_pause_policy|admin_set_billing_stop_pause_policy/);
  assert.match(page, /async function rpc\(name,args=\{\}\)[\s\S]*?const token=session\?\.access_token[\s\S]*?localApiBase\(\)\+'\/rest\/v1\/rpc\//);
  assert.match(page, /const RELAY_RPC_NAMES=new Set\(\['wol_relay_status'/);
  assert.match(page, /admin_get_billing_stop_pause_policy/);
  assert.match(page, /admin_set_billing_stop_pause_policy/);
});

test('DB Android localhost endpoint and install identity are preserved', () => {
  assert.match(page, /http:\/\/127\.0\.0\.1:8787/);
  assert.doesNotMatch(page, /http:\/\/127\.0\.0\.1:8788/);
  assert.match(index, /http:\/\/127\.0\.0\.1:8787/);
  assert.match(control, /http:\/\/127\.0\.0\.1:8787/);
  assert.match(gradle, /applicationId 'com\.anigames\.billingadmin\.v153db'/);
  assert.match(gradle, /versionCode 83/);
  assert.match(gradle, /versionName '12\.1\.56'/);
  assert.match(manifest, /android:label="AniGames Admin V12\.1\.56 DB Android"/);
});

test('Remote Play, reports, rental, Billing Control and WoL functions remain present', () => {
  for (const token of [
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
    'wol_relay_probe_status',
    'V12.1.56-STOP-PAUSE-OWNER-ROLE-VISIBILITY',
  ]) assert.ok(page.includes(token), 'missing retained feature: ' + token);
  assert.match(page, /startLocalAdmin\(\);/);
  assert.doesNotMatch(page, /startDualDbAdmin\(\);/);
});
