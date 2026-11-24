import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const gateway = 'https://ani-games-db-android-stage-gateway.anigamesready.workers.dev';
const legacyRelay = 'ani-games-db-android-stage-ws-relay.anigamesready.workers.dev';
const pages = {
  admin: readFileSync('android/app/src/main/assets/web/admin.html', 'utf8'),
  login: readFileSync('android/app/src/main/assets/web/index.html', 'utf8'),
  control: readFileSync('android/app/src/main/assets/web/admin-control.html', 'utf8'),
};
const page = pages.admin;
const gradle = readFileSync('android/app/build.gradle', 'utf8');
const manifest = readFileSync('android/app/src/main/AndroidManifest.xml', 'utf8');

test('All DB Android pages use the public stage-gateway and migrate old relay/loopback addresses', () => {
  for (const [name, source] of Object.entries(pages)) {
    assert.ok(source.includes(gateway), name + ' is missing the canonical gateway URL');
    assert.ok(source.includes('ANI-ADMIN-V12.1.58-CANONICAL-STAGE-GATEWAY'), name + ' is missing gateway marker');
    assert.doesNotMatch(source, /http:\/\/127\.0\.0\.1:878[78]/, name + ' still has a loopback URL');
    assert.ok(!source.includes('https://' + legacyRelay), name + ' still targets the internal ws-relay URL');
    assert.ok(source.includes(legacyRelay), name + ' lost the one-time legacy URL migration guard');
    assert.match(source, /function localApiBase\(\)/);
    assert.match(source, /localStorage\.setItem\(LOCAL_API_KEY,ONLINE_GATEWAY_URL\)/);
  }
  assert.match(pages.admin, /Login memakai DB Android Ani Games Ready melalui gateway aman menuju Redmi/);
  assert.match(pages.admin, /Alamat Gateway DB Android/);
  assert.match(pages.login, /ALAMAT GATEWAY DB ANDROID/);
});

test('V12.1.53 startup helper is now defined before it is called', () => {
  assert.equal((page.match(/function setAdminAuthEnabled\(enabled\)/g) || []).length, 1);
  assert.equal((page.match(/setAdminAuthEnabled\(/g) || []).length, 6);
  assert.ok(page.indexOf('function setAdminAuthEnabled(enabled)') < page.indexOf('async function ensureActiveDbRouteForAuth()'));
  assert.ok(page.indexOf('function setAdminAuthEnabled(enabled)') < page.indexOf('async function startLocalAdmin()'));
  assert.match(page, /function setAdminAuthEnabled\(enabled\)\{[\s\S]*?loginSubmitting==='true'/);
});

test('Primary Admin login keeps the V12.1.53 Auth endpoint and token contract', () => {
  const loginFn = page.match(/async function login\(\)\{[\s\S]*?\n\}/)?.[0] || '';
  assert.match(loginFn, /localJson\('\/auth\/v1\/token\?grant_type=password'/);
  assert.match(loginFn, /email:username,password/);
  assert.match(loginFn, /session\?\.access_token/);
  assert.match(loginFn, /session\?\.refresh_token/);
  assert.match(loginFn, /storeAdminRefreshToken\(session\.refresh_token\)/);
  assert.match(loginFn, /await boot\(\)/);
  assert.match(page, /async function rpc\(name,args=\{\}\)[\s\S]*?\/rest\/v1\/rpc\//);
  assert.match(page, /rpc\('admin_context'\)/);
  assert.match(page, /async function relayAccessToken\(\)/);
  assert.match(page, /async function signup\(\)/);
});

test('Separate Supabase Blynk/WoL authentication cannot block Admin login', () => {
  const loginFn = page.match(/async function login\(\)\{[\s\S]*?\n\}/)?.[0] || '';
  assert.doesNotMatch(loginFn, /await sb\.auth\.signInWithPassword/);
  assert.match(loginFn, /Promise\.resolve\(sb\.auth\.signInWithPassword/);
  assert.match(loginFn, /Blynk\/WoL relay authentication unavailable/);
  assert.match(page, /const RELAY_RPC_NAMES=new Set/);
  assert.match(page, /wol_relay_probe_request/);
});

test('Login stage failures are returned to the login screen with a useful stage and HTTP error', () => {
  assert.match(page, /GATEWAY_NETWORK_ERROR/);
  assert.match(page, /HTTP '\+response\.status/);
  assert.match(page, /Gateway Redmi belum siap:/);
  assert.match(page, /Login Admin gagal:/);
  assert.match(page, /Login token diterima, tetapi dashboard gagal pada tahap/);
  assert.match(page, /return false;\s*\}\s*\}\s*async function startLocalAdmin/);
});

test('Stop/Pause, Free Test, Pairing, Remote Play and WoL contracts remain', () => {
  for (const token of [
    'V12.1.51-BILLING-STOP-PAUSE-POLICY',
    'billingStopPausePolicyNav',
    'admin_get_billing_stop_pause_policy',
    'admin_set_billing_stop_pause_policy',
    'freeTestPolicyNav',
    'admin_get_free_test_policy',
    'admin_set_free_test_policy',
    'pairingNav',
    'admin_remote_play_dashboard',
    'admin_remote_play_set_host_permission',
    'admin_remote_play_set_rental_permission',
    'admin_remote_play_issue_client_credential',
    'admin_remote_play_issue_host_enrollment',
    'wol_relay_probe_request',
  ]) assert.ok(page.includes(token), 'missing preserved V12.1.53 feature: ' + token);
  assert.match(page, /function billingStopPausePolicyIsOwner\(\)\{return typeof isWakeRelayOwner==='function'&&isWakeRelayOwner\(\)===true\}/);
  assert.match(page, /function isRemotePlayOwner\(\)\{return typeof isWakeRelayOwner==='function'&&isWakeRelayOwner\(\)===true\}/);
  assert.match(page, /function freeTestPolicyIsOwner\(\)\{[\s\S]*?isWakeRelayOwner\(\)===true/);
});

test('APK package identity is isolated from installed V12.1.53', () => {
  assert.match(gradle, /applicationId 'com\.anigames\.billingadmin\.v158online'/);
  assert.doesNotMatch(gradle, /applicationId 'com\.anigames\.billingadmin\.v153db'/);
  assert.match(gradle, /versionCode 85/);
  assert.match(gradle, /versionName '12\.1\.58'/);
  assert.match(manifest, /android:label="AniGames Admin Online V12\.1\.58 SAFE TEST"/);
});
