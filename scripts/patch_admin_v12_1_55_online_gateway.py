#!/usr/bin/env python3
"""Build V12.1.55 as an online Admin app using the verified DB Android gateway.

This is a post-patch overlay on V12.1.53/V12.1.54. It changes only the API
default URL, displayed build identity and isolated test package ID.
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
MARKER = "ANI-ADMIN-V12.1.55-ONLINE-GATEWAY-DEFAULT"
PAGES = ("admin.html", "index.html", "admin-control.html")

for name in PAGES:
    path = WEB / name
    if not path.is_file():
        raise SystemExit("ADMIN_WEB_PAGE_MISSING: " + name)
    source = path.read_text(encoding="utf-8")
    if MARKER in source:
        if GATEWAY not in source:
            raise SystemExit("ONLINE_GATEWAY_MARKER_MISMATCH: " + name)
    else:
        old_count = sum(source.count(url) for url in OLD_URLS)
        if old_count < 1:
            raise SystemExit("EXPECTED_LOCAL_DEFAULT_NOT_FOUND: " + name)
        for url in OLD_URLS:
            source = source.replace(url, GATEWAY)
        anchor = "function localApiBase(){"
        if source.count(anchor) != 1:
            raise SystemExit("LOCAL_API_BASE_ANCHOR_NOT_UNIQUE: " + name)
        source = source.replace(anchor, "// " + MARKER + "\n" + anchor, 1)

    source = source.replace(
        "Login memakai database lokal Ani Games Ready. Alamat awal adalah server di perangkat ini.",
        "Login memakai DB Android Ani Games Ready melalui gateway HTTPS."
    )
    source = source.replace("Admin Dashboard • DB Android Lokal", "Admin Dashboard • DB Android Online")
    source = source.replace("Billing Control • DB Android Lokal", "Billing Control • DB Android Online")
    source = source.replace("Alamat API Lokal", "Alamat Gateway DB Android")
    source = source.replace("Server lokal terhubung.", "Gateway DB Android terhubung.")
    for url in OLD_URLS:
        if url in source:
            raise SystemExit("LOOPBACK_URL_REMAINS: " + name)
    if GATEWAY not in source or MARKER not in source:
        raise SystemExit("ONLINE_GATEWAY_DEFAULT_VERIFY_FAILED: " + name)
    path.write_text(source, encoding="utf-8")

if not GRADLE.is_file() or not MANIFEST.is_file():
    raise SystemExit("ADMIN_ANDROID_IDENTITY_FILES_MISSING")
gradle = GRADLE.read_text(encoding="utf-8")
manifest = MANIFEST.read_text(encoding="utf-8")

if gradle.count("versionCode 82") != 1 or gradle.count("versionName '12.1.54'") != 1:
    raise SystemExit("V12.1.54_GRADLE_VERSION_ANCHOR_MISMATCH")
gradle = gradle.replace("versionCode 82", "versionCode 83", 1)
gradle = gradle.replace("versionName '12.1.54'", "versionName '12.1.55'", 1)

if gradle.count("applicationId 'com.anigames.billingadmin.v153db'") != 1:
    raise SystemExit("ADMIN_BASE_PACKAGE_ID_ANCHOR_MISMATCH")
gradle = gradle.replace(
    "applicationId 'com.anigames.billingadmin.v153db'",
    "applicationId 'com.anigames.billingadmin.v155online'",
    1
)

label_old = 'android:label="AniGames Admin V12.1.54 DB Android"'
label_new = 'android:label="AniGames Admin Online V12.1.55"'
if manifest.count(label_old) != 1:
    raise SystemExit("ADMIN_MANIFEST_LABEL_ANCHOR_MISMATCH")
manifest = manifest.replace(label_old, label_new, 1)

if "versionCode 83" not in gradle or "versionName '12.1.55'" not in gradle:
    raise SystemExit("V12.1.55_GRADLE_VERSION_VERIFY_FAILED")
if "applicationId 'com.anigames.billingadmin.v155online'" not in gradle:
    raise SystemExit("V12.1.55_PACKAGE_ID_VERIFY_FAILED")

GRADLE.write_text(gradle, encoding="utf-8")
MANIFEST.write_text(manifest, encoding="utf-8")
VERSION.write_text(
    "AniGames Admin Online V12.1.55 — V12.1.53/V12.1.54 core preserved; remote DB Android HTTPS gateway default; separate install package for safe testing.\n",
    encoding="utf-8"
)

# Keep the working adapter, RPC contracts and pairing feature; only change its base URL.
admin = (WEB / "admin.html").read_text(encoding="utf-8")
for required in (
    "startLocalAdmin();",
    "admin_remote_play_dashboard",
    "admin_remote_play_set_host_permission",
    "admin_remote_play_set_rental_permission",
    "admin_remote_play_issue_client_credential",
    "admin_remote_play_issue_host_enrollment",
    "admin_rental_accounts_global",
    "admin_command_status",
    "wol_relay_probe_request",
):
    if required not in admin:
        raise SystemExit("ADMIN_CORE_OR_PAIRING_FEATURE_MISSING: " + required)
if "startDualDbAdmin();" in admin or "DB2_ROUTE_KEY" in admin:
    raise SystemExit("UNREQUESTED_DUAL_DB_ROUTING_REINTRODUCED")
print("PASS: V12.1.55 uses the verified HTTPS gateway on login, dashboard and Billing Control.")
print("PASS: V12.1.53/V12.1.54 Admin core, Remote Play pairing RPCs and WoL sidecar are retained.")
print("PASS: isolated package ID prevents overwriting the currently installed stable Admin app.")
