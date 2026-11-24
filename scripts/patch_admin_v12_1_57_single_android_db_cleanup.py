#!/usr/bin/env python3
"""V12.1.57: remove legacy dual-database UI and route remnants.

Keeps the local Android DB as the only Admin/Rental/Remote Play backend.
The existing Blynk/WoL relay remains an explicitly separate relay sidecar
until the Android DB server provides an equivalent, verified relay API.
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
MARKER = "V12.1.57-SINGLE-ANDROID-DB-ADMIN"

for path in (PAGE, GRADLE, MANIFEST):
    if not path.is_file():
        raise SystemExit("REQUIRED_FILE_MISSING:" + str(path))

page = PAGE.read_text(encoding="utf-8")
gradle = GRADLE.read_text(encoding="utf-8")
manifest = MANIFEST.read_text(encoding="utf-8")

if MARKER in page:
    if (
        "versionCode 84" in gradle
        and "versionName '12.1.57'" in gradle
        and "applicationId 'com.anigames.billingadmin.v157dbtest'" in gradle
    ):
        print("PASS: V12.1.57 single-Android-DB cleanup already applied.")
        raise SystemExit(0)
    raise SystemExit("V12.1.57_MARKER_METADATA_MISMATCH")

if "V12.1.56-STOP-PAUSE-OWNER-ROLE-VISIBILITY" not in page:
    raise SystemExit("EXPECTED_V12_1_56_BASELINE_MISSING")
if "startLocalAdmin();" not in page or "startDualDbAdmin();" in page:
    raise SystemExit("LOCAL_ADMIN_STARTUP_BASELINE_MISMATCH")
if "async function ensureActiveDbRouteForAuth()" not in page:
    raise SystemExit("LOCAL_ANDROID_DB_HEALTH_CHECK_ANCHOR_MISSING")
if "const RELAY_RPC_NAMES=new Set(" not in page or "admin_remote_play_dashboard" not in page:
    raise SystemExit("REMOTE_PLAY_OR_RELAY_ADAPTER_MISSING")


def remove_balanced_element(source: str, start: int, tag: str) -> str:
    """Remove one balanced HTML element starting at an exact opening tag."""
    token_re = re.compile(r"<" + re.escape(tag) + r"\b[^>]*>|</" + re.escape(tag) + r"\s*>", re.I)
    depth = 0
    for match in token_re.finditer(source, start):
        token = match.group(0)
        if token.startswith("</"):
            depth -= 1
            if depth == 0:
                return source[:start] + source[match.end():]
        else:
            depth += 1
    raise SystemExit("UNBALANCED_HTML_ELEMENT:" + tag)


def remove_element_by_attr(source: str, tag: str, attr: str, value: str) -> tuple[str, int]:
    pattern = re.compile(
        r"<" + re.escape(tag) + r"\b[^>]*\b" + re.escape(attr)
        + r"\s*=\s*['\"]" + re.escape(value) + r"['\"][^>]*>",
        re.I,
    )
    matches = list(pattern.finditer(source))
    if len(matches) != 1:
        raise SystemExit(f"EXPECTED_ONE_{tag.upper()}_{attr}_{value}_FOUND_{len(matches)}")
    match = matches[0]
    return remove_balanced_element(source, match.start(), tag), len(matches)


# Remove the old global DB switch strip, rather than merely hiding it with CSS.
page, _ = remove_element_by_attr(page, "div", "class", "db-switch card")
# Remove the entire hidden DB1/DB2 sync/preflight section.
page, _ = remove_element_by_attr(page, "section", "id", "databaseTools")
# Remove the legacy navigation entry.
nav_pattern = re.compile(
    r"<button\b(?=[^>]*\bdata-tab\s*=\s*['\"]databaseTools['\"])[^>]*>.*?</button>",
    re.I | re.S,
)
page, removed_nav = nav_pattern.subn("", page, count=1)
if removed_nav != 1:
    raise SystemExit("DATABASE_TOOLS_NAV_REMOVAL_FAILED")


def clean_css_rules(source: str) -> str:
    """Remove legacy-only selector rules while preserving shared selectors."""
    rule_re = re.compile(r"([^{}]+)\{([^{}]*)\}")

    def repl(match: re.Match) -> str:
        selector_text, body = match.group(1), match.group(2)
        selectors = [s.strip() for s in selector_text.split(",")]
        kept = [
            s for s in selectors
            if not any(k in s.lower() for k in (".db-switch", "#databasetools", "databasetools"))
        ]
        if not kept:
            return ""
        if len(kept) == len(selectors):
            return match.group(0)
        return ",".join(kept) + "{" + body + "}"

    previous = None
    while previous != source:
        previous = source
        source = rule_re.sub(repl, source)
    source = re.sub(
        r"/\* DB Android branch: legacy Supabase DB1/DB2 route UI is intentionally unavailable\. \*/\s*",
        "",
        source,
    )
    return source


style_pattern = re.compile(r"(<style\b[^>]*>)(.*?)(</style>)", re.I | re.S)
style_matches = list(style_pattern.finditer(page))
if len(style_matches) != 1:
    raise SystemExit("ADMIN_STYLE_BLOCK_COUNT_MISMATCH:" + str(len(style_matches)))
page = style_pattern.sub(
    lambda m: m.group(1) + clean_css_rules(m.group(2)) + m.group(3),
    page,
    count=1,
)

# The local /health probe is a simple Android DB availability check, not a DB route resolver.
page = page.replace("ensureActiveDbRouteForAuth", "checkAndroidDbReady")

# The Admin and all core functions always use the configured local Android DB endpoint.
# The Supabase client below is retained only for the existing Blynk/WoL relay sidecar.
old_constants = (
    "const DB1_URL='https://wzkjpycjizexxcxrfdvr.supabase.co';\n"
    "const DB1_KEY='sb_publishable_DobdCrOd43-vluON5gV7hg_6Js2Ea5V';\n"
    "const DB2_URL='',DB2_KEY='',DB1_ROUTE_KEY='',DB2_ROUTE_KEY='';\n"
    "const DB_ROUTE_NOTICE_KEY='ani_games_db_android_notice_v1';"
)
new_constants = (
    "const WOL_RELAY_SUPABASE_URL='https://wzkjpycjizexxcxrfdvr.supabase.co';\n"
    "const WOL_RELAY_SUPABASE_ANON_KEY='sb_publishable_DobdCrOd43-vluON5gV7hg_6Js2Ea5V';\n"
    "const WOL_RELAY_FUNCTION_URL=WOL_RELAY_SUPABASE_URL+'/functions/v1/ani-games-api';"
)
if page.count(old_constants) != 1:
    raise SystemExit("LEGACY_DATABASE_CONSTANT_BLOCK_MISMATCH")
page = page.replace(old_constants, new_constants, 1)
page = page.replace(
    "let DB_TARGET='local',SB_URL=DB1_URL,SB_KEY=DB1_KEY,SB_FUNCTION_URL=DB1_URL+'/functions/v1/ani-games-api';\n",
    "",
)
page = page.replace(
    "let DB_ROUTE_EPOCH=0,DB_ROUTE_SWITCH_ID=null,dualDbRouteReady=true,dualDbRouteLocked=false;\n",
    "const ADMIN_BACKEND_LABEL='Android DB';\n",
)
page = page.replace("DB1_URL", "WOL_RELAY_SUPABASE_URL")
page = page.replace("DB1_KEY", "WOL_RELAY_SUPABASE_ANON_KEY")
page = page.replace("SB_KEY", "WOL_RELAY_SUPABASE_ANON_KEY")
page = page.replace("SB_FUNCTION_URL", "WOL_RELAY_FUNCTION_URL")
page = re.sub(r"\(DB_TARGET==='backup'\?'DB2':'DB1'\)", "ADMIN_BACKEND_LABEL", page)
page = page.replace("String(DB_TARGET||'primary')", "'android'")

# Remove no-op compatibility handlers and old selector entry point.
for name in ("requestGlobalDbSwitch", "v12DbTargetChanged", "v12InitDbSwitch", "v12SaveDbTarget", "openDbSelector"):
    pattern = re.compile(
        r"(?m)(?:^|(?<=\n))(?:async\s+)?function\s+" + re.escape(name) + r"\s*\([^)]*\)\s*\{[^{}]*\}"
    )
    page, count = pattern.subn("", page)
    if count != 1:
        raise SystemExit(f"LEGACY_HANDLER_REMOVAL_FAILED:{name}:{count}")

# Remove the branch that used to block a tab open for the hidden dual-DB section.
page, tab_guard_count = re.subn(
    r"if\(id==='databaseTools'\)\{msg\('Database & Sync [^']+ tidak tersedia pada cabang DB Android\.',true\);return;\}",
    "",
    page,
    count=1,
)
if tab_guard_count != 1:
    raise SystemExit("DATABASE_TOOLS_TAB_GUARD_NOT_FOUND")

# Replace outdated DB1/DB2 wording in local-backend health/alert labels.
page = page.replace("DB Android Lokal • multi-tenant • audit • reporting", "Android DB • multi-tenant • audit • reporting")
page = page.replace("DB1/DB2", "Android DB")
page = page.replace("DB1", "Android DB")
page = page.replace("DB2", "Android DB")

# Final source checks: no dual-database UI, variables, selectors, handlers, or routing concepts.
for obsolete in (
    "databaseTools", "db-switch", "DB1", "DB2", "DB_TARGET", "DB_ROUTE_EPOCH",
    "DB_ROUTE_SWITCH_ID", "dualDbRouteReady", "dualDbRouteLocked", "DB_ROUTE_NOTICE_KEY",
    "DB1_URL", "DB2_URL", "DB1_KEY", "DB2_KEY", "requestGlobalDbSwitch",
    "v12DbTargetChanged", "v12InitDbSwitch", "v12SaveDbTarget", "openDbSelector",
    "ensureActiveDbRouteForAuth", "startDualDbAdmin",
):
    if obsolete in page:
        raise SystemExit("LEGACY_DUAL_DB_REMAINS:" + obsolete)
for required in (
    "const LOCAL_API_KEY=", "http://127.0.0.1:8787", "async function checkAndroidDbReady()",
    "async function login()", "localJson('/auth/v1/token?grant_type=password'",
    "async function rpc(name,args={})", "const RELAY_RPC_NAMES=new Set(",
    "admin_remote_play_dashboard", "remotePlayAdminNav", "admin_get_free_test_policy",
    "admin_get_billing_stop_pause_policy", "report_detailed_usage_page", "admin_rental_accounts_global",
    "wakeRelayCard", "wol_relay_enqueue", "startLocalAdmin();",
):
    if required not in page:
        raise SystemExit("ANDROID_DB_OR_CORE_FEATURE_MISSING:" + required)

# Keep the relay as an independent service, not as a second rental database.
if "const WOL_RELAY_FUNCTION_URL=WOL_RELAY_SUPABASE_URL+'/functions/v1/ani-games-api';" not in page:
    raise SystemExit("WOL_RELAY_SIDECAR_URL_MISSING")
scripts = re.findall(r"<script\b(?![^>]*\bsrc=)[^>]*>(.*?)</script>", page, re.I | re.S)
if len(scripts) != 1:
    raise SystemExit("ADMIN_INLINE_SCRIPT_COUNT_MISMATCH:" + str(len(scripts)))

# Use a side-by-side SAFE TEST identity; never overwrite installed stable Admin packages.
if gradle.count("versionCode 83") != 1 or gradle.count("versionName '12.1.56'") != 1:
    raise SystemExit("ADMIN_GRADLE_V12_1_56_ANCHOR_MISMATCH")
if gradle.count("applicationId 'com.anigames.billingadmin.v156dbtest'") != 1:
    raise SystemExit("ADMIN_V12_1_56_TEST_PACKAGE_ANCHOR_MISMATCH")
gradle = gradle.replace("versionCode 83", "versionCode 84", 1)
gradle = gradle.replace("versionName '12.1.56'", "versionName '12.1.57'", 1)
gradle = gradle.replace(
    "applicationId 'com.anigames.billingadmin.v156dbtest'",
    "applicationId 'com.anigames.billingadmin.v157dbtest'",
    1,
)
old_label = 'android:label="AniGames Admin DB Android V12.1.56 SAFE TEST"'
new_label = 'android:label="AniGames Admin DB Android V12.1.57 SAFE TEST"'
if manifest.count(old_label) != 1:
    raise SystemExit("ADMIN_MANIFEST_V12_1_56_LABEL_ANCHOR_MISMATCH")
manifest = manifest.replace(old_label, new_label, 1)

page += "\n<!-- " + MARKER + " -->\n"
PAGE.write_text(page, encoding="utf-8")
GRADLE.write_text(gradle, encoding="utf-8")
MANIFEST.write_text(manifest, encoding="utf-8")
VERSION.write_text(
    "AniGames Admin DB Android V12.1.57 SAFE TEST — single local Android DB; isolated package com.anigames.billingadmin.v157dbtest; legacy dual-DB UI/handlers removed; Blynk/WoL relay remains a separate sidecar.\n",
    encoding="utf-8",
)
print("PASS: DB1/DB2 switch strip, nav entry and sync/preflight section removed from Admin APK.")
print("PASS: legacy DB1/DB2 routing constants, variables, no-op handlers and login naming removed.")
print("PASS: login, dashboard and core RPC continue through the local Android DB API on port 8787.")
print("PASS: Remote Play, rental, reporting, Free Test, PAUSE/STOP and WoL relay controls retained.")
print("PASS: sidecar endpoint clearly names itself WOL relay; SAFE TEST package bumped to V12.1.57.")
