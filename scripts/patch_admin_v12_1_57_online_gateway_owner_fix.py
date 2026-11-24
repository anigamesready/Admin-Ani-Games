#!/usr/bin/env python3
"""Admin DB Android V12.1.57: V12.1.53 base + HTTPS gateway + Owner role fix.

This is a side-by-side SAFE TEST build. It preserves the V12.1.53 Admin core,
keeps the isolated DB Android RPC adapter, and changes only the server default,
display labels, Owner gates and app identity.
"""
from pathlib import Path
import re
import sys

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
WEB = ROOT / "android/app/src/main/assets/web"
GRADLE = ROOT / "android/app/build.gradle"
MANIFEST = ROOT / "android/app/src/main/AndroidManifest.xml"
VERSION = ROOT / "VERSION.txt"

GATEWAY = "https://ani-games-db-android-stage-ws-relay.anigamesready.workers.dev"
OLD_URLS = ("http://127.0.0.1:8787", "http://127.0.0.1:8788")
GATEWAY_MARKER = "ANI-ADMIN-V12.1.57-ONLINE-GATEWAY-DEFAULT"
ROLE_MARKER = "V12.1.57-STOP-PAUSE-OWNER-ROLE-VISIBILITY"
BASE_MARKER = "V12.1.53-REMOTE-PLAY-SHARED-DB-PORT-8787"
POLICY_MARKER = "V12.1.51-BILLING-STOP-PAUSE-POLICY"
BASE_PACKAGE_ID = "com.anigames.billingadmin.v153db"
TEST_PACKAGE_ID = "com.anigames.billingadmin.v157online"
PAGES = ("admin.html", "index.html", "admin-control.html")

for p in (WEB / "admin.html", WEB / "index.html", WEB / "admin-control.html", GRADLE, MANIFEST):
    if not p.is_file():
        raise SystemExit("REQUIRED_ADMIN_SOURCE_MISSING:" + str(p))

page = (WEB / "admin.html").read_text(encoding="utf-8")
if BASE_MARKER not in page:
    raise SystemExit("EXPECTED_V12_1_53_BASELINE_MISSING")
if POLICY_MARKER not in page:
    raise SystemExit("V12_1_51_STOP_PAUSE_MENU_MISSING")
if "function isWakeRelayOwner()" not in page:
    raise SystemExit("CANONICAL_MASTER_OWNER_RESOLVER_MISSING")

# 1. Restore the known V12.1.55 HTTPS gateway as the default on every Admin page.
for name in PAGES:
    path = WEB / name
    source = path.read_text(encoding="utf-8")
    if GATEWAY_MARKER not in source:
        replacements = 0
        for old in OLD_URLS:
            count = source.count(old)
            if count:
                source = source.replace(old, GATEWAY)
                replacements += count
        if replacements < 1:
            raise SystemExit("EXPECTED_V12_1_53_LOOPBACK_DEFAULT_NOT_FOUND:" + name)
        anchor = "function localApiBase(){"
        if source.count(anchor) != 1:
            raise SystemExit("LOCAL_API_BASE_ANCHOR_NOT_UNIQUE:" + name)
        source = source.replace(anchor, "// " + GATEWAY_MARKER + "\n" + anchor, 1)

    source = source.replace(
        "Login memakai database lokal Ani Games Ready. Alamat awal adalah server di perangkat ini.",
        "Login memakai DB Android Ani Games Ready melalui gateway HTTPS."
    )
    source = source.replace("Admin Dashboard • DB Android Lokal", "Admin Dashboard • DB Android Online")
    source = source.replace("Billing Control • DB Android Lokal", "Billing Control • DB Android Online")
    source = source.replace("Alamat API Lokal", "Alamat Gateway DB Android")
    source = source.replace("Server lokal terhubung.", "Gateway DB Android terhubung.")

    for old in OLD_URLS:
        if old in source:
            raise SystemExit("LOOPBACK_DEFAULT_REMAINS:" + name + ":" + old)
    if GATEWAY not in source or GATEWAY_MARKER not in source:
        raise SystemExit("ONLINE_GATEWAY_DEFAULT_VERIFY_FAILED:" + name)
    if "DB Android Lokal" in source or "Alamat API Lokal" in source:
        raise SystemExit("LOCAL_LOGIN_LABEL_REMAINS:" + name)
    path.write_text(source, encoding="utf-8")

# 2. Reuse the canonical Master/Owner alias resolver for all relevant menus.
def replace_function(source: str, name: str, replacement: str) -> str:
    pattern = re.compile(r"(?ms)^function " + re.escape(name) + r"\(\)\s*\{.*?^\}")
    source, count = pattern.subn(lambda _: replacement, source, count=1)
    if count != 1:
        raise SystemExit("OWNER_FUNCTION_ANCHOR_MISMATCH:" + name)
    return source

page = (WEB / "admin.html").read_text(encoding="utf-8")
page = replace_function(
    page, "billingStopPausePolicyIsOwner",
    "function billingStopPausePolicyIsOwner(){try{return typeof isWakeRelayOwner==='function'&&isWakeRelayOwner()===true}catch(_){return false}}"
)
page = replace_function(
    page, "freeTestPolicyIsOwner",
    "function freeTestPolicyIsOwner(){try{return typeof isWakeRelayOwner==='function'&&isWakeRelayOwner()===true}catch(_){return false}}"
)
page = replace_function(
    page, "isRemotePlayOwner",
    "function isRemotePlayOwner(){try{return typeof isWakeRelayOwner==='function'&&isWakeRelayOwner()===true}catch(_){return false}}"
)

# The V12.1.53 UI contains the Owner-only pairing, Free Test and Stop/Pause entries.
apply_start = page.find("function applyPairingRoleUI(){")
apply_end = page.find("function selectOrg(){", apply_start)
if apply_start < 0 or apply_end <= apply_start:
    raise SystemExit("ADMIN_OWNER_MENU_VISIBILITY_FUNCTION_BOUNDARY_MISMATCH")
new_apply = """function applyPairingRoleUI(){
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
page = page[:apply_start] + new_apply + page[apply_end:]

# Normalize tab guards, but do not add a new tab or change the V12.1.53 navigation.
page = page.replace(
    "if(id==='pairing'&&ctx?.role!=='owner')return;",
    "if(id==='pairing'&&!isWakeRelayOwner())return;"
)

open_pattern = re.compile(r"(?m)^function openBillingStopPausePolicyMenu\(\)\s*\{")
page, open_count = open_pattern.subn(
    "function openBillingStopPausePolicyMenu(){\n if(!billingStopPausePolicyIsOwner())return msg('Akses PAUSE / STOP BILLING hanya untuk Master/Owner.',true);",
    page, count=1
)
if open_count != 1:
    raise SystemExit("STOP_PAUSE_OPEN_MENU_ANCHOR_MISMATCH")

load_pattern = re.compile(r"(?m)^async function loadBillingStopPausePolicy\(\)\s*\{")
page, load_count = load_pattern.subn(
    "async function loadBillingStopPausePolicy(){\n if(!billingStopPausePolicyIsOwner()){billingStopPausePolicyMessage('Hanya Master/Owner yang boleh melihat dan mengubah izin PAUSE / STOP.',true);return null;}",
    page, count=1
)
if load_count != 1:
    raise SystemExit("STOP_PAUSE_LOAD_POLICY_ANCHOR_MISMATCH")

# Save already has a Master/Owner check in V12.1.51. Keep it and fail closed on errors.
page += "\n<!-- " + ROLE_MARKER + " -->\n"
for token in (
    ROLE_MARKER,
    "function billingStopPausePolicyIsOwner(){try{return typeof isWakeRelayOwner==='function'&&isWakeRelayOwner()===true}catch(_){return false}}",
    "function freeTestPolicyIsOwner(){try{return typeof isWakeRelayOwner==='function'&&isWakeRelayOwner()===true}catch(_){return false}}",
    "function isRemotePlayOwner(){try{return typeof isWakeRelayOwner==='function'&&isWakeRelayOwner()===true}catch(_){return false}}",
    "const owner=billingStopPausePolicyIsOwner();",
    "if(!billingStopPausePolicyIsOwner())return msg('Akses PAUSE / STOP BILLING hanya untuk Master/Owner.',true);",
    "admin_get_billing_stop_pause_policy",
    "admin_set_billing_stop_pause_policy",
):
    if token not in page:
        raise SystemExit("V12_1_57_ASSERTION_FAILED:" + token)
for element_id in (
    "billingStopPausePolicyNav", "billingStopPausePolicyCard",
    "billingStopPausePolicySwitch", "billingStopPausePolicySave",
):
    if page.count('id="' + element_id + '"') != 1:
        raise SystemExit("STOP_PAUSE_ELEMENT_DUPLICATE_OR_MISSING:" + element_id)
if "admin_get_billing_stop_pause_policy" in page and "admin_set_billing_stop_pause_policy" in page:
    allow = re.search(r"const RELAY_RPC_NAMES=new Set\(\[(.*?)\]\);", page, re.S)
    if not allow:
        raise SystemExit("RELAY_RPC_ALLOWLIST_NOT_FOUND")
    for name in ("admin_get_billing_stop_pause_policy", "admin_set_billing_stop_pause_policy"):
        if name in allow.group(1):
            raise SystemExit("POLICY_RPC_WRONGLY_ROUTED_TO_RELAY:" + name)
if "startLocalAdmin();" not in page or "startDualDbAdmin();" in page:
    raise SystemExit("V12_1_53_DB_ANDROID_STARTUP_ADAPTER_CHANGED")
if "function localJson(" not in page or "localApiBase()+'/rest/v1/rpc/'" not in page:
    raise SystemExit("DB_ANDROID_ADMIN_RPC_ADAPTER_MISSING")
if "admin_remote_play_dashboard" not in page or "wol_relay_probe_request" not in page:
    raise SystemExit("V12_1_53_REMOTE_PLAY_OR_WOL_FEATURE_MISSING")

(WEB / "admin.html").write_text(page, encoding="utf-8")

# 3. Use a new side-by-side package. Never create an APK that could overwrite the
# installed V12.1.53 stable package with a different CI signing certificate.
gradle = GRADLE.read_text(encoding="utf-8")
manifest = MANIFEST.read_text(encoding="utf-8")
if gradle.count("versionCode 81") != 1 or gradle.count("versionName '12.1.53'") != 1:
    raise SystemExit("V12_1_53_GRADLE_VERSION_ANCHOR_MISMATCH")
if gradle.count("applicationId '" + BASE_PACKAGE_ID + "'") != 1:
    raise SystemExit("V12_1_53_APPLICATION_ID_MISMATCH")
gradle = gradle.replace("applicationId '" + BASE_PACKAGE_ID + "'", "applicationId '" + TEST_PACKAGE_ID + "'", 1)
gradle = gradle.replace("versionCode 81", "versionCode 84", 1)
gradle = gradle.replace("versionName '12.1.53'", "versionName '12.1.57'", 1)

label_old = 'android:label="AniGames Admin V12.1.53 DB Android"'
label_new = 'android:label="AniGames Admin Online V12.1.57 SAFE TEST"'
if manifest.count(label_old) != 1:
    raise SystemExit("V12_1_53_MANIFEST_LABEL_MISMATCH")
manifest = manifest.replace(label_old, label_new, 1)

for name in ("admin.html", "index.html", "admin-control.html"):
    source = (WEB / name).read_text(encoding="utf-8")
    if GATEWAY not in source or GATEWAY_MARKER not in source:
        raise SystemExit("ONLINE_GATEWAY_NOT_SET_IN_FINAL_PAGE:" + name)
    for old in OLD_URLS:
        if old in source:
            raise SystemExit("LOOPBACK_URL_REMAINS_IN_FINAL_PAGE:" + name)
GRADLE.write_text(gradle, encoding="utf-8")
MANIFEST.write_text(manifest, encoding="utf-8")
VERSION.write_text(
    "AniGames Admin Online V12.1.57 SAFE TEST — based on V12.1.53 source; HTTPS DB Android gateway default; separate package com.anigames.billingadmin.v157online.\\n",
    encoding="utf-8"
)
print("PASS: V12.1.53 source baseline retained; all three Admin pages default to the HTTPS gateway.")
print("PASS: PAUSE/STOP, Free Test and Remote Play owner UI use the canonical Master/Owner resolver.")
print("PASS: local DB Android API is not used as the login/server default; Supabase WoL relay remains separate.")
print("PASS: SAFE TEST package is side-by-side and cannot overwrite installed V12.1.53.")
