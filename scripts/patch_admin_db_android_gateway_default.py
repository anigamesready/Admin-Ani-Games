#!/usr/bin/env python3
"""V12.1.52: default the isolated Admin DB Android APK to its verified Redmi Cloudflare gateway."""
from pathlib import Path
import re
import sys

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
WEB = ROOT / "android/app/src/main/assets/web"
GATEWAY = "https://ani-games-db-android-stage-ws-relay.anigamesready.workers.dev"
LOOPBACK = "http://127.0.0.1:8788"
MARKER = "ANI-DB-ANDROID-REMOTE-GATEWAY-DEFAULT-V1"
PAGES = ("admin.html", "index.html", "admin-control.html")

for name in PAGES:
    path = WEB / name
    if not path.is_file():
        raise SystemExit("ADMIN_API_PAGE_NOT_FOUND: " + name)
    source = path.read_text(encoding="utf-8")
    if MARKER in source:
        if GATEWAY not in source or LOOPBACK in source:
            raise SystemExit("REMOTE_GATEWAY_MARKER_BUT_DEFAULT_MISMATCH: " + name)
        print("PASS: remote gateway default already applied to " + name)
        continue

    count = source.count(LOOPBACK)
    if count < 1:
        raise SystemExit("EXPECTED_LOOPBACK_DEFAULT_MISSING: " + name)
    source = source.replace(LOOPBACK, GATEWAY)

    anchor = "function localApiBase(){"
    if source.count(anchor) != 1:
        raise SystemExit("LOCAL_API_BASE_ANCHOR_NOT_UNIQUE: " + name)
    source = source.replace(anchor, "// " + MARKER + "\n" + anchor, 1)

    source = source.replace(
        "Login memakai database lokal Ani Games Ready. Alamat awal adalah server di perangkat ini.",
        "Login memakai DB Android Ani Games Ready melalui gateway aman menuju Redmi."
    )
    source = source.replace("Admin Dashboard • DB Android Lokal", "Admin Dashboard • DB Android")
    source = source.replace("Billing Control • DB Android Lokal", "Billing Control • DB Android")
    source = source.replace("Alamat API Lokal", "Alamat Gateway DB Android")
    source = source.replace("Server lokal terhubung.", "Server DB Android terhubung.")
    path.write_text(source, encoding="utf-8")
    print(f"PASS: {name}: {count} loopback default(s) replaced with the verified HTTPS gateway")

gradle_path = ROOT / "android/app/build.gradle"
manifest_path = ROOT / "android/app/src/main/AndroidManifest.xml"
version_path = ROOT / "VERSION_ADMIN_ANDROID.txt"
if not gradle_path.is_file() or not manifest_path.is_file():
    raise SystemExit("ADMIN_ANDROID_BUILD_IDENTITY_FILES_MISSING")

gradle = gradle_path.read_text(encoding="utf-8")
manifest = manifest_path.read_text(encoding="utf-8")
gradle, code_count = re.subn(r"\bversionCode\s+79\b", "versionCode 80", gradle, count=1)
gradle, name_count = re.subn(r"versionName\s*'12\.1\.51'", "versionName '12.1.52'", gradle, count=1)
if code_count != 1 or name_count != 1:
    raise SystemExit("V12.1.52_GRADLE_VERSION_ANCHOR_MISMATCH")

old_label = 'android:label="AniGames Admin V12.1.51 DB Android"'
new_label = 'android:label="AniGames Admin V12.1.52 DB Android"'
if manifest.count(old_label) != 1:
    raise SystemExit("V12.1.52_MANIFEST_LABEL_ANCHOR_MISMATCH")
manifest = manifest.replace(old_label, new_label, 1)

gradle_path.write_text(gradle, encoding="utf-8")
manifest_path.write_text(manifest, encoding="utf-8")
version_path.write_text(
    "AniGames Admin Android V12.1.52 DB Android — defaults to the dedicated Redmi DB Android HTTPS WebSocket gateway; keeps manual API URL override, isolated package ID, and independent WoL relay sidecar.\n",
    encoding="utf-8"
)

for name in PAGES:
    source = (WEB / name).read_text(encoding="utf-8")
    if MARKER not in source or GATEWAY not in source or LOOPBACK in source:
        raise SystemExit("V12.1.52_REMOTE_DEFAULT_VERIFY_FAILED: " + name)
    if "127.0.0.1:8787" in source:
        raise SystemExit("LEGACY_MAIN_SERVER_PORT_REFERENCED: " + name)

admin = (WEB / "admin.html").read_text(encoding="utf-8")
if "startLocalAdmin();" not in admin or "startDualDbAdmin();" in admin:
    raise SystemExit("DB_ANDROID_SINGLE_DATABASE_STARTUP_REGRESSION")
for required in (
    "admin_rental_accounts_global", "admin_create_rental_global",
    "admin_update_rental_global", "admin_delete_rental_global",
    "report_detailed_usage_page", "report_rental_period_breakdown",
    "admin_command", "admin_command_status",
    "relayAccessToken()", "wol_relay_probe_request",
    "sb.schema('api').rpc(name,args)"
):
    if required not in admin:
        raise SystemExit("ADMIN_CORE_OR_SEPARATE_WOL_FUNCTION_MISSING: " + required)

for forbidden in ("startDualDbAdmin();", "DB2_ROUTE_KEY", "requestSharedDbRouteSwitch"):
    if forbidden in admin:
        raise SystemExit("LEGACY_DB1_DB2_ROUTING_RETURNED: " + forbidden)

if "versionCode 80" not in gradle or "versionName '12.1.52'" not in gradle:
    raise SystemExit("V12.1.52_BUILD_IDENTITY_VERIFY_FAILED")
if "applicationId 'com.anigames.billingadmin.v150db'" not in gradle:
    raise SystemExit("DB_ANDROID_PACKAGE_ID_CHANGED")
if new_label not in manifest:
    raise SystemExit("V12.1.52_MANIFEST_VERIFY_FAILED")

print("PASS: V12.1.52 remote gateway is the default for Admin, Billing Control login and control pages.")
print("PASS: local override is retained; Admin single-DB Android adapter and primary features remain.")
print("PASS: Supabase usage remains limited to the independent WoL relay sidecar.")
print("PASS: DB1/DB2 routing is not re-enabled; isolated applicationId preserved.")
