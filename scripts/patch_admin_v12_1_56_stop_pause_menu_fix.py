#!/usr/bin/env python3
"""Admin DB Android V12.1.56: restore Owner PAUSE/STOP menu visibility safely.

Uses the canonical V12.1.49 Master/Owner resolver, retains the V12.1.53
local DB Android package/port, and does not alter any database or relay config.
"""
from pathlib import Path
import re
import sys

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
WEB = ROOT / "android/app/src/main/assets/web"
PAGE = WEB / "admin.html"
GRADLE = ROOT / "android/app/build.gradle"
MANIFEST = ROOT / "android/app/src/main/AndroidManifest.xml"
VERSION = ROOT / "VERSION.txt"

MARKER = "V12.1.56-STOP-PAUSE-OWNER-ROLE-VISIBILITY"
BASE_MARKER = "V12.1.54-PAIRING-REMOTE-PLAY-LABEL"
BASE_PACKAGE_ID = "com.anigames.billingadmin.v153db"
TEST_PACKAGE_ID = "com.anigames.billingadmin.v156dbtest"
PACKAGE_ID = TEST_PACKAGE_ID

for p in (PAGE, GRADLE, MANIFEST):
    if not p.is_file():
        raise SystemExit("REQUIRED_ADMIN_DB_ANDROID_FILE_MISSING:" + str(p))

page = PAGE.read_text(encoding="utf-8")
gradle = GRADLE.read_text(encoding="utf-8")
manifest = MANIFEST.read_text(encoding="utf-8")

if MARKER in page:
    if (
        "function billingStopPausePolicyIsOwner(){try{return typeof isWakeRelayOwner==='function'&&isWakeRelayOwner()===true}catch(_){return false}}" in page
        and "versionCode 83" in gradle
        and "versionName '12.1.56'" in gradle
        and f"applicationId '{PACKAGE_ID}'" in gradle
    ):
        print("PASS: Admin V12.1.56 Stop/Pause Owner visibility fix already applied")
        raise SystemExit(0)
    raise SystemExit("V12.1.56_MARKER_METADATA_MISMATCH")

if BASE_MARKER not in page:
    raise SystemExit("EXPECTED_V12_1_54_BASELINE_MISSING")
if "V12.1.51-BILLING-STOP-PAUSE-POLICY" not in page:
    raise SystemExit("V12.1.51_POLICY_MENU_NOT_PRESENT_IN_BASELINE")
for token in (
    "billingStopPausePolicyNav",
    "billingStopPausePolicyCard",
    "billingStopPausePolicySwitch",
    "billingStopPausePolicySave",
    "admin_get_billing_stop_pause_policy",
    "admin_set_billing_stop_pause_policy",
    "function isWakeRelayOwner()",
):
    if token not in page:
        raise SystemExit("REQUIRED_POLICY_OR_OWNER_RESOLVER_MISSING:" + token)

# Normalize the other Owner-only feature controls to the same canonical resolver.
# This fixes aliases consistently across Free Test, Pairing PC, Remote Play and Stop/Pause.
free_test_owner = "function freeTestPolicyIsOwner(){try{return typeof isWakeRelayOwner==='function'&&isWakeRelayOwner()===true}catch(_){return false}}"
page, free_test_count = re.subn(
    r"(?ms)^function freeTestPolicyIsOwner\(\)\s*\{.*?^\}",
    lambda _: free_test_owner,
    page,
    count=1,
)
if free_test_count != 1:
    raise SystemExit("FREE_TEST_OWNER_ROLE_ANCHOR_MISMATCH")

remote_owner_old = "function isRemotePlayOwner(){return String(ctx?.role||'').trim().toLowerCase()==='owner';}"
remote_owner_new = "function isRemotePlayOwner(){try{return typeof isWakeRelayOwner==='function'&&isWakeRelayOwner()===true}catch(_){return false}}"
if page.count(remote_owner_old) != 1:
    raise SystemExit("REMOTE_PLAY_OWNER_ROLE_ANCHOR_MISMATCH")
page = page.replace(remote_owner_old, remote_owner_new, 1)

pairing_tab_old = "function tab(id){if(id==='pairing'&&ctx?.role!=='owner')return;if(id==='remotePlay'&&!isRemotePlayOwner())return;"
pairing_tab_new = "function tab(id){if(id==='pairing'&&!isWakeRelayOwner())return;if(id==='remotePlay'&&!isRemotePlayOwner())return;"
if page.count(pairing_tab_old) != 1:
    raise SystemExit("PAIRING_TAB_OWNER_ROLE_ANCHOR_MISMATCH")
page = page.replace(pairing_tab_old, pairing_tab_new, 1)

# V12.1.49 owns the canonical role aliases. Reuse it instead of maintaining a
# narrower copy that only recognizes 'owner'/'super_admin'.
old_owner_fn = "function billingStopPausePolicyIsOwner(){const role=String(ctx?.role||'').trim().toLowerCase();return role==='owner'||role==='super_admin';}"
new_owner_fn = "function billingStopPausePolicyIsOwner(){try{return typeof isWakeRelayOwner==='function'&&isWakeRelayOwner()===true}catch(_){return false}}"
if page.count(old_owner_fn) != 1:
    raise SystemExit("STOP_PAUSE_OWNER_GUARD_ANCHOR_MISMATCH")
page = page.replace(old_owner_fn, new_owner_fn, 1)

# Replace the complete Owner-only menu visibility function. The old body declared
# freeTestNav once from a narrow role check; patching only part of it caused a
# duplicate const declaration. Rebuild this one function with a single resolver.
apply_ui_start = page.find("function applyPairingRoleUI(){")
apply_ui_end = page.find("function selectOrg(){", apply_ui_start)
if apply_ui_start < 0 or apply_ui_end <= apply_ui_start:
    raise SystemExit("ADMIN_OWNER_MENU_VISIBILITY_FUNCTION_BOUNDARY_MISMATCH")
new_apply_ui = """function applyPairingRoleUI(){
 const owner=billingStopPausePolicyIsOwner();
 const freeTestNav=$('freeTestPolicyNav');if(freeTestNav)freeTestNav.classList.toggle('hidden',!owner);
 const freeTestCard=$('freeTestPolicyCard');if(freeTestCard)freeTestCard.classList.toggle('hidden',!owner);
 const stopPauseNav=$('billingStopPausePolicyNav');if(stopPauseNav)stopPauseNav.classList.toggle('hidden',!owner);
 const stopPauseCard=$('billingStopPausePolicyCard');if(stopPauseCard)stopPauseCard.classList.toggle('hidden',!owner);
 const nav=$('pairingNav'),sec=$('pairing');
 if(nav)nav.classList.toggle('hidden',!owner);
 if(sec)sec.classList.toggle('hidden',!owner);
 if(owner)$('enrollOrg').innerHTML=orgs.map(o=>'<option value="'+o.id+'">'+esc(o.name)+' • '+o.kind+'</option>').join('');
}
"""
page = page[:apply_ui_start] + new_apply_ui + page[apply_ui_end:]

# Guard the custom menu entry point and read RPC as well as the save action.
open_anchor = "function openBillingStopPausePolicyMenu(){\n"
open_guard = "function openBillingStopPausePolicyMenu(){\n if(!billingStopPausePolicyIsOwner())return msg('Akses PAUSE / STOP BILLING hanya untuk Master/Owner.',true);\n"
if page.count(open_anchor) != 1:
    raise SystemExit("STOP_PAUSE_OPEN_MENU_ANCHOR_MISMATCH")
page = page.replace(open_anchor, open_guard, 1)

load_anchor = "async function loadBillingStopPausePolicy(){\n"
load_guard = (
    "async function loadBillingStopPausePolicy(){\n"
    " if(!billingStopPausePolicyIsOwner()){"
    "billingStopPausePolicyMessage('Hanya Master/Owner yang boleh melihat dan mengubah izin PAUSE / STOP.',true);"
    "return null;"
    "}\n"
)
if page.count(load_anchor) != 1:
    raise SystemExit("STOP_PAUSE_LOAD_FUNCTION_ANCHOR_MISMATCH")
page = page.replace(load_anchor, load_guard, 1)

# Keep the control fail-closed if a save fails: read the server's last confirmed
# value again, and only display that value as authoritative.
old_catch = (
    " }catch(e){if(sw)sw.disabled=true;"
    "billingStopPausePolicyMessage('SIMPAN GAGAL / STATUS TIDAK DIKETAHUI. Muat ulang status dari database. Detail: '+String(e?.message||e).slice(0,180),true);}"
)
new_catch = (
    " }catch(e){"
    "const detail=String(e?.message||e).slice(0,160);"
    "if(sw)sw.disabled=true;"
    "const confirmed=await loadBillingStopPausePolicy();"
    "billingStopPausePolicyMessage("
    "'SIMPAN GAGAL: '+detail+'. '+(confirmed?'Status dikembalikan ke nilai terakhir yang dikonfirmasi database.':'Status database belum dapat diverifikasi; kontrol tetap dikunci.'),"
    "true"
    ");"
    "}"
)
if page.count(old_catch) != 1:
    raise SystemExit("STOP_PAUSE_SAVE_FAILURE_ANCHOR_MISMATCH")
page = page.replace(old_catch, new_catch, 1)

old_finally = " finally{save.disabled=!billingStopPausePolicyIsOwner();}"
new_finally = " finally{const state=$('billingStopPausePolicyState');save.disabled=!billingStopPausePolicyIsOwner()||state?.textContent==='GAGAL MEMUAT';}"
if page.count(old_finally) != 1:
    raise SystemExit("STOP_PAUSE_SAVE_FINAL_STATE_ANCHOR_MISMATCH")
page = page.replace(old_finally, new_finally, 1)

# Verify the local RPC adapter stays on DB Android (not the Supabase/Blynk
# sidecar) and that both policy RPCs are routed through the Admin token.
if "const RELAY_RPC_NAMES=new Set(['wol_relay_status'" not in page:
    raise SystemExit("RELAY_ONLY_SUPABASE_ALLOWLIST_MISSING")
if "admin_get_billing_stop_pause_policy" in page and "admin_set_billing_stop_pause_policy" in page:
    # The Admin local adapter is expected to keep these RPC names outside the
    # RELAY_RPC_NAMES allow-list so rpc() uses the local DB Android API.
    m = re.search(r"const RELAY_RPC_NAMES=new Set\(\[(.*?)\]\);", page, re.S)
    if not m:
        raise SystemExit("RELAY_RPC_ALLOWLIST_NOT_FOUND")
    allow = m.group(1)
    for name in ("admin_get_billing_stop_pause_policy", "admin_set_billing_stop_pause_policy"):
        if name in allow:
            raise SystemExit("POLICY_RPC_MUST_USE_LOCAL_DB_ANDROID_API:" + name)

# Bump the package version and use a side-by-side test applicationId; leave the saved local API port unchanged.
if gradle.count("versionCode 82") != 1 or gradle.count("versionName '12.1.54'") != 1:
    raise SystemExit("ADMIN_GRADLE_V12_1_54_VERSION_ANCHOR_MISMATCH")
if gradle.count(f"applicationId '{BASE_PACKAGE_ID}'") != 1:
    raise SystemExit("ADMIN_DB_ANDROID_BASE_PACKAGE_ID_MISMATCH")
# Keep V12.1.53 installed. This APK is side-by-side SAFE TEST because CI debug signing differs.
gradle = gradle.replace(f"applicationId '{BASE_PACKAGE_ID}'", f"applicationId '{TEST_PACKAGE_ID}'", 1)
gradle = gradle.replace("versionCode 82", "versionCode 83", 1)
gradle = gradle.replace("versionName '12.1.54'", "versionName '12.1.56'", 1)

label_old = 'android:label="AniGames Admin V12.1.54 DB Android"'
label_new = 'android:label="AniGames Admin DB Android V12.1.56 SAFE TEST"'
if manifest.count(label_old) != 1:
    raise SystemExit("ADMIN_MANIFEST_V12_1_54_LABEL_MISMATCH")
manifest = manifest.replace(label_old, label_new, 1)

for name in ("admin.html", "index.html", "admin-control.html"):
    source = (WEB / name).read_text(encoding="utf-8")
    if "http://127.0.0.1:8787" not in source or "http://127.0.0.1:8788" in source:
        raise SystemExit("ADMIN_DB_ANDROID_PORT_8787_MUST_BE_PRESERVED:" + name)

page += "\n<!-- " + MARKER + " -->\n"
for token in (
    MARKER,
    "function billingStopPausePolicyIsOwner(){try{return typeof isWakeRelayOwner==='function'&&isWakeRelayOwner()===true}catch(_){return false}}",
    "const owner=billingStopPausePolicyIsOwner();",
    "if(!billingStopPausePolicyIsOwner())return msg('Akses PAUSE / STOP BILLING hanya untuk Master/Owner.',true);",
    "admin_get_billing_stop_pause_policy",
    "admin_set_billing_stop_pause_policy",
    "SIMPAN GAGAL:",
):
    if token not in page:
        raise SystemExit("V12.1.56_ASSERTION_FAILED:" + token)

if page.count('id="billingStopPausePolicyNav"') != 1:
    raise SystemExit("STOP_PAUSE_NAV_DUPLICATE_OR_MISSING")
if page.count('id="billingStopPausePolicyCard"') != 1:
    raise SystemExit("STOP_PAUSE_CARD_DUPLICATE_OR_MISSING")
if page.count('id="billingStopPausePolicySwitch"') != 1:
    raise SystemExit("STOP_PAUSE_SWITCH_DUPLICATE_OR_MISSING")
if page.count('id="billingStopPausePolicySave"') != 1:
    raise SystemExit("STOP_PAUSE_SAVE_BUTTON_DUPLICATE_OR_MISSING")
if "owner==='super_admin'" in page or "role==='owner'||role==='super_admin'" in page:
    raise SystemExit("NARROW_STOP_PAUSE_OWNER_CHECK_REMAINS")

PAGE.write_text(page, encoding="utf-8")
GRADLE.write_text(gradle, encoding="utf-8")
MANIFEST.write_text(manifest, encoding="utf-8")
VERSION.write_text(
    "AniGames Admin DB Android V12.1.56 SAFE TEST — isolated package com.anigames.billingadmin.v156dbtest; V12.1.53 stable app and data remain installed; local API port 8787.\n",
    encoding="utf-8",
)
print("PASS: Master/Owner aliases show PAUSE / STOP menu through the canonical role resolver.")
print("PASS: menu open, policy read, and save are Owner-gated; failed saves re-read the last DB-confirmed value.")
print("PASS: V12.1.53 stable package remains installed; SAFE TEST uses a separate package ID and local API port 8787.")
print("PASS: Remote Play, Blynk/WoL sidecar and Admin core remain unchanged.")
