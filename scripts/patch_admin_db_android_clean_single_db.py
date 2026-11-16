#!/usr/bin/env python3
"""V12.1.53: physically strip legacy DB1/DB2 routes/UI from the isolated Admin DB Android app."""
from pathlib import Path
import re
import sys

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
WEB = ROOT / "android/app/src/main/assets/web"
GATEWAY = "https://ani-games-db-android-stage-ws-relay.anigamesready.workers.dev"
LOOPBACK = "http://127.0.0.1:8788"
REMOTE_MARKER = "ANI-DB-ANDROID-REMOTE-GATEWAY-DEFAULT-V1"
CLEAN_MARKER = "ANI-DB-ANDROID-CLEAN-SINGLE-DB-V1"
PAGES = ("admin.html", "index.html", "admin-control.html")

def remove_once(source: str, pattern: str, label: str, flags=re.S) -> str:
    updated, count = re.subn(pattern, "", source, count=1, flags=flags)
    if count != 1:
        raise SystemExit(f"V12.1.53_EXPECTED_ONE_{label}: found {count}")
    return updated

def remove_css_rules(css: str) -> str:
    targets = (
        ".db-switch", "#databaseTools", "#dbActiveBadge", "#dbSystemStatusBadge",
        "#dbRouteStatusHint", "#globalDbTarget", "#db1Health", "#db2Health",
        "#dualDbReadiness", "#dbSync"
    )
    # Remove only the matching simple CSS declaration blocks, including rules inside @media.
    changed = True
    while changed:
        changed = False
        for target in targets:
            pattern = re.compile(r"(^|[{}])(\s*[^{}]*" + re.escape(target) + r"[^{}]*)\{[^{}]*\}", re.M)
            css, n = pattern.subn(lambda m: m.group(1), css)
            if n:
                changed = True
    # Remove empty media blocks left only after their DB switch rules were stripped.
    css = re.sub(r"@media\s*\([^{}]*\)\s*\{\s*\}", "", css)
    return css

# Clean the Admin page only. Login and Billing Control already use one local API adapter.
admin_path = WEB / "admin.html"
if not admin_path.is_file():
    raise SystemExit("ADMIN_DB_ANDROID_PAGE_NOT_FOUND")
admin = admin_path.read_text(encoding="utf-8")
if CLEAN_MARKER not in admin:
    if admin.count('<div class="db-switch card"') != 1:
        raise SystemExit("LEGACY_GLOBAL_DB_SWITCH_BAR_NOT_UNIQUE")
    admin = remove_once(
        admin,
        r'<div class="db-switch card"[^>]*>.*?(?=<div class="shell">)',
        "GLOBAL_DB_SWITCH_BAR"
    )
    admin = remove_once(
        admin,
        r'<button\b(?=[^>]*data-tab="databaseTools")[^>]*>.*?</button>',
        "DATABASE_TOOLS_NAV_BUTTON"
    )
    admin = remove_once(
        admin,
        r'<section id="databaseTools" class="section">.*?</section>',
        "DATABASE_TOOLS_SECTION"
    )

    # Remove the DB1/DB2 conditional from the mobile/desktop tab wrapper, keeping the normal tab action.
    legacy_tab = "if(id==='databaseTools'){msg('Database & Sync DB1/DB2 tidak tersedia pada cabang DB Android.',true);return;}"
    if admin.count(legacy_tab) != 1:
        raise SystemExit("LEGACY_DATABASE_TAB_GUARD_NOT_UNIQUE")
    admin = admin.replace(legacy_tab, "", 1)

    legacy_stub = re.compile(
        r"function\s+requestGlobalDbSwitch\(\)\{msg\('Perpindahan DB1/DB2 tidak tersedia pada cabang DB Android\.',true\)\}\s*"
        r"function\s+v12DbTargetChanged\(\)\{\}\s*"
        r"function\s+v12InitDbSwitch\(\)\{\}\s*"
        r"async\s+function\s+v12SaveDbTarget\(\)\{msg\('DB Android memakai satu server lokal; menu perpindahan DB dinonaktifkan\.',true\)\}"
    )
    admin, stub_count = legacy_stub.subn("", admin, count=1)
    if stub_count != 1:
        raise SystemExit(f"LEGACY_DB_SWITCH_STUB_BLOCK_NOT_UNIQUE: {stub_count}")

    if admin.count("function openDbSelector(){requestGlobalDbSwitch()}") != 1:
        raise SystemExit("LEGACY_DB_SELECTOR_STUB_NOT_UNIQUE")
    admin = admin.replace("function openDbSelector(){requestGlobalDbSwitch()}", "", 1)

    # These route-switch variables are not used by the local Admin adapter.
    old_state = "let DB_TARGET='local',SB_URL=DB1_URL,SB_KEY=DB1_KEY,SB_FUNCTION_URL=DB1_URL+'/functions/v1/ani-games-api';\nlet DB_ROUTE_EPOCH=0,DB_ROUTE_SWITCH_ID=null,dualDbRouteReady=true,dualDbRouteLocked=false;"
    new_state = "const RELAY_SUPABASE_FUNCTION_URL=RELAY_SUPABASE_URL+'/functions/v1/ani-games-api';"
    if admin.count(old_state) != 1:
        raise SystemExit("LEGACY_DB_ROUTE_STATE_NOT_UNIQUE")
    admin = admin.replace(old_state, new_state, 1)

    # Supabase credentials/client are retained only for the independent Blynk/WoL sidecar.
    admin = admin.replace("const DB1_URL=", "const RELAY_SUPABASE_URL=", 1)
    admin = admin.replace("const DB1_KEY=", "const RELAY_SUPABASE_PUBLISHABLE_KEY=", 1)
    admin = admin.replace("supabase.createClient(DB1_URL,DB1_KEY,", "supabase.createClient(RELAY_SUPABASE_URL,RELAY_SUPABASE_PUBLISHABLE_KEY,", 1)
    admin = admin.replace("SB_FUNCTION_URL", "RELAY_SUPABASE_FUNCTION_URL")
    admin = admin.replace("SB_KEY", "RELAY_SUPABASE_PUBLISHABLE_KEY")
    if "DB1_URL" in admin or "DB1_KEY" in admin:
        raise SystemExit("OLD_DB1_CREDENTIAL_SYMBOL_REMAINS")

    admin = admin.replace("\nconst DB_ROUTE_NOTICE_KEY='ani_games_db_android_notice_v1';", "")
    # Remove stale DB1/DB2 status wording from notification, alert-cache and recovery messages.
    replacements = {
        "Koneksi server lokal gagal • '+(DB_TARGET==='backup'?'DB2':'DB1')+' • percobaan berulang dibatasi":
            "Koneksi server DB Android gagal • percobaan berulang dibatasi",
        "text+' • '+(DB_TARGET==='backup'?'DB2':'DB1')+' • cek koneksi server lokal":
            "text+' • cek koneksi server DB Android",
        "const dbLabel=String(DB_TARGET||'primary');\n const seenKey='ani_admin_alert_seen_v1_'+dbLabel+'_'+String(currentOrg.id);":
            "const seenKey='ani_admin_alert_seen_v1_'+String(currentOrg.id);",
        "Sinkronisasi alert rental bermasalah • '+(DB_TARGET==='backup'?'DB2':'DB1')":
            "Sinkronisasi alert rental DB Android bermasalah'",
        "Enrollment pemulihan berhasil dibuat pada database yang sedang dipilih. Pastikan DB2 sudah menerima migrasi SQL pemulihan jika DB2 digunakan.":
            "Enrollment pemulihan berhasil dibuat pada database DB Android."
    }
    for old, new in replacements.items():
        if admin.count(old) != 1:
            raise SystemExit("STALE_DB_ROUTE_TEXT_NOT_UNIQUE: " + old[:90])
        admin = admin.replace(old, new, 1)

    # Remove DB1/DB2-only styles. Keep the existing recovery password panel hidden.
    admin, style_count = re.subn(
        r"/\* DB Android branch: legacy Supabase DB1/DB2 route UI is intentionally unavailable\. \*/\s*\.db-switch,#databaseTools,\.nav \[data-tab=\"databaseTools\"\],button\[onclick\*=\"databaseTools\"\],#recovery\{display:none!important\}",
        "#recovery{display:none!important}",
        admin,
        count=1
    )
    if style_count != 1:
        raise SystemExit("LEGACY_DB_HIDDEN_CSS_BLOCK_NOT_FOUND")
    style_matches = list(re.finditer(r"<style[^>]*>(.*?)</style>", admin, re.S | re.I))
    if len(style_matches) != 1:
        raise SystemExit("ADMIN_STYLE_BLOCK_NOT_UNIQUE")
    style = style_matches[0].group(1)
    cleaned_style = remove_css_rules(style)
    admin = admin[:style_matches[0].start(1)] + cleaned_style + admin[style_matches[0].end(1):]

    # Neutralize historic branding comments which named the old dual-DB selector.
    admin = admin.replace("palette borrowed from the approved DB-switch UI preview; existing layout/logic preserved.",
                          "existing layout and core Admin behavior preserved.")

    # Mark after all legacy artifacts have been physically removed.
    anchor = "const LOCAL_API_KEY='ani_games_ready_db_android_api_url_v1';"
    if admin.count(anchor) != 1:
        raise SystemExit("LOCAL_API_CONFIG_ANCHOR_NOT_UNIQUE")
    admin = admin.replace(anchor, "// " + CLEAN_MARKER + "\n" + anchor, 1)
    admin_path.write_text(admin, encoding="utf-8")
else:
    print("PASS: clean single-DB marker already applied")

# Validate each app page has the remote Redmi gateway as its only default, not an on-device loopback.
for name in PAGES:
    path = WEB / name
    if not path.is_file():
        raise SystemExit("ADMIN_API_PAGE_NOT_FOUND: " + name)
    source = path.read_text(encoding="utf-8")
    if GATEWAY not in source or LOOPBACK in source or "127.0.0.1:8787" in source:
        raise SystemExit("REMOTE_GATEWAY_DEFAULT_MISMATCH: " + name)
    if REMOTE_MARKER not in source:
        raise SystemExit("REMOTE_GATEWAY_MARKER_MISSING: " + name)

admin = admin_path.read_text(encoding="utf-8")
legacy_tokens = (
    "databaseTools", "DB_ROUTE", "DB_TARGET", "DB2", "DB1_URL", "DB1_KEY",
    "DB2_URL", "DB2_KEY", "dualDb", "dbSync", "db-switch", "globalDbTarget",
    "checkBothDbApis", "requestGlobalDbSwitch", "openDbSelector",
    "v12DbTargetChanged", "v12InitDbSwitch", "v12SaveDbTarget"
)
for token in legacy_tokens:
    if token in admin:
        raise SystemExit("LEGACY_DUAL_DB_TOKEN_REMAINS: " + token)

# Main Admin data/auth must continue to use the DB Android API; WoL must remain a distinct sidecar.
required_admin = (
    "startLocalAdmin();", "admin_context", "admin_devices",
    "admin_rental_accounts_global", "admin_create_rental_global",
    "admin_update_rental_global", "admin_delete_rental_global",
    "admin_command", "admin_command_status",
    "report_detailed_usage_page", "report_monthly_rental_summary",
    "report_rental_period_breakdown", "save_theme",
    "localJson('/auth/v1/token?grant_type=password'"
)
for token in required_admin:
    if token not in admin:
        raise SystemExit("ADMIN_DB_ANDROID_CORE_FUNCTION_MISSING: " + token)
if "startDualDbAdmin();" in admin or "sb.from(" in admin:
    raise SystemExit("LEGACY_DB_STARTUP_OR_DIRECT_SUPABASE_TABLE_ACCESS_REMAINS")

required_relay = (
    "const RELAY_SUPABASE_URL=", "const RELAY_SUPABASE_PUBLISHABLE_KEY=",
    "supabase.createClient(RELAY_SUPABASE_URL,RELAY_SUPABASE_PUBLISHABLE_KEY,",
    "RELAY_SUPABASE_FUNCTION_URL+'/iot/status'",
    "RELAY_SUPABASE_FUNCTION_URL+'/iot/power'",
    "relayAccessToken()", "wol_relay_probe_request", "wol_relay_probe_status",
    "wol_relay_create_enrollment", "wol_relay_enqueue"
)
for token in required_relay:
    if token not in admin:
        raise SystemExit("INDEPENDENT_WOL_RELAY_SIDECAR_MISSING: " + token)

# Increment only the isolated DB Android package identity.
gradle_path = ROOT / "android/app/build.gradle"
manifest_path = ROOT / "android/app/src/main/AndroidManifest.xml"
version_path = ROOT / "VERSION_ADMIN_ANDROID.txt"
for path in (gradle_path, manifest_path):
    if not path.is_file():
        raise SystemExit("ADMIN_ANDROID_BUILD_IDENTITY_FILES_MISSING: " + str(path))
gradle = gradle_path.read_text(encoding="utf-8")
manifest = manifest_path.read_text(encoding="utf-8")
gradle, code_count = re.subn(r"\bversionCode\s+80\b", "versionCode 81", gradle, count=1)
gradle, name_count = re.subn(r"versionName\s*'12\.1\.52'", "versionName '12.1.53'", gradle, count=1)
if code_count != 1 or name_count != 1:
    raise SystemExit("V12.1.53_GRADLE_VERSION_ANCHOR_MISMATCH")
old_label = 'android:label="AniGames Admin V12.1.52 DB Android"'
new_label = 'android:label="AniGames Admin V12.1.53 DB Android"'
if manifest.count(old_label) != 1:
    raise SystemExit("V12.1.53_MANIFEST_LABEL_ANCHOR_MISMATCH")
manifest = manifest.replace(old_label, new_label, 1)
gradle_path.write_text(gradle, encoding="utf-8")
manifest_path.write_text(manifest, encoding="utf-8")
version_path.write_text(
    "AniGames Admin Android V12.1.53 DB Android — physically removes legacy DB1/DB2 selector, sync and route-control UI; keeps the Redmi HTTPS gateway as default, local Admin API, original Admin features and independent WoL relay sidecar.\n",
    encoding="utf-8"
)

if "versionCode 81" not in gradle or "versionName '12.1.53'" not in gradle:
    raise SystemExit("V12.1.53_BUILD_IDENTITY_VERIFY_FAILED")
if "applicationId 'com.anigames.billingadmin.v150db'" not in gradle:
    raise SystemExit("DB_ANDROID_PACKAGE_ID_CHANGED")
if new_label not in manifest:
    raise SystemExit("V12.1.53_MANIFEST_VERIFY_FAILED")

print("PASS: legacy DB1/DB2 route bar, tab, sync section, stubs and route-state removed physically.")
print("PASS: Android Admin core functions still use the single Redmi DB Android API.")
print("PASS: Supabase client remains only as the separately named Blynk/WoL relay sidecar.")
print("PASS: gateway defaults retained in Admin, login and Billing Control pages.")
print("PASS: package identity preserved; version is 12.1.53 / versionCode 81.")
