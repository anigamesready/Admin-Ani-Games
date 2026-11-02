from pathlib import Path
import re

HTML = Path("android/app/src/main/assets/web/admin.html")
GRADLE = Path("android/app/build.gradle")
VERSION = Path("VERSION.txt")

if not HTML.is_file() or not GRADLE.is_file():
    raise SystemExit("Admin Android source root is missing.")

html = HTML.read_text(encoding="utf-8")
gradle = GRADLE.read_text(encoding="utf-8")
marker = "V12.1.40-ADMIN-NO-SHUTDOWN"
if marker in html:
    if "versionCode 68" in gradle and "versionName '12.1.40'" in gradle:
        print("PASS: Admin V12.1.40 shutdown-timer removal already applied.")
        raise SystemExit(0)
    raise SystemExit("V12.1.40 marker/version mismatch; refusing to continue.")

if "V12.1.39-AUTO-RELAY-TARGET-ONLY" not in html:
    raise SystemExit("Expected exact Admin V12.1.39 target-only WoL baseline.")
if "versionCode 67" not in gradle or "versionName '12.1.39'" not in gradle:
    raise SystemExit("Expected exact Admin V12.1.39 Gradle version metadata.")

# Remove only the timer card; keep the rest of the PC/device section intact.
card_start = html.find('<div class="card" id="pcShutdownTimerCard"')
card_end = html.find('\n</section>\n\n<section id="pairing"', card_start)
if card_start < 0 or card_end < 0:
    raise SystemExit("Shutdown timer card boundaries are missing or ambiguous.")
card = html[card_start:card_end]
if "shutdownHours" not in card or "shutdownMinutes" not in card or "shutdownSeconds" not in card:
    raise SystemExit("Timer card does not match the expected hour/minute/second UI.")
html = html[:card_start] + html[card_end:]

# Remove the dedicated navigation entry without affecting the database tools nav.
nav = '<button id="shutdownTimerNav" onclick="openShutdownTimerMenu()">⏱️ Timer Shutdown PC</button>'
if html.count(nav) != 1:
    raise SystemExit("Expected exactly one dedicated Timer Shutdown PC navigation entry.")
html = html.replace(nav, "", 1)

# Remove the timer controller and its menu navigation helper as one isolated block.
helpers_start = html.find("function openShutdownTimerMenu() {")
helpers_end = html.find("async function loadDevices(){", helpers_start)
if helpers_start < 0 or helpers_end < 0:
    raise SystemExit("Shutdown timer JavaScript block boundaries are missing.")
helper_block = html[helpers_start:helpers_end]
for required in ("function schedulePcShutdown()", "function cancelPcShutdown()",
                 "p_command: 'schedule_shutdown'", "p_command: 'cancel_shutdown_timer'",
                 "ADMIN_PC_SHUTDOWN_STATE_KEY", "setInterval(updateShutdownTimerStatus"):
    if required not in helper_block:
        raise SystemExit("Expected timer controller component not found: " + required)
html = html[:helpers_start] + html[helpers_end:]

# The V12.1.29 owner-only UI toggle included timer-only references. Remove those
# two clauses while retaining the FREE TEST panel's role gating.
for fragment in (
    "const shutdownNav=$('shutdownTimerNav');if(shutdownNav)shutdownNav.classList.toggle('hidden',!owner);",
    "const shutdownCard=$('pcShutdownTimerCard');if(shutdownCard)shutdownCard.classList.toggle('hidden',!owner);",
):
    if html.count(fragment) != 1:
        raise SystemExit("Timer-only role-gating fragment count mismatch.")
    html = html.replace(fragment, "", 1)

# Device-list refresh must continue to populate global PC selector and recovery list;
# timer-only dropdown initialization is no longer needed.
call = "refreshShutdownTargetOptions(rows);"
if html.count(call) != 1:
    raise SystemExit("Expected exactly one timer-only device dropdown refresh call.")
html = html.replace(call, "", 1)

# Update version metadata for this removal-only Admin release.
gradle, c = re.subn(r"\bversionCode\s+67\b", "versionCode 68", gradle, count=1)
gradle, n = re.subn(r"versionName\s*'12\.1\.39'", "versionName '12.1.40'", gradle, count=1)
if c != 1 or n != 1:
    raise SystemExit("Could not safely update V12.1.39 Gradle version metadata.")

# Add a verifiable marker and update VERSION.txt.
needle = "V12.1.39-AUTO-RELAY-TARGET-ONLY"
html = html.replace(needle, needle + " • " + marker, 1)
VERSION.write_text(
    "AniGames Admin Android V12.1.40 — removes all Admin PC shutdown countdown UI and scheduling/cancel command paths. Keeps login, pairing/recovery, rental, reseller, dashboard/report, WoL and dual-DB routing.\n",
    encoding="utf-8"
)

# Regression assertions: the timer feature is absent, while adjacent features remain.
for forbidden in (
    "pcShutdownTimerCard", "shutdownTimerNav", "shutdownHours", "shutdownMinutes",
    "shutdownSeconds", "schedulePcShutdown", "cancelPcShutdown",
    "schedule_shutdown", "cancel_shutdown_timer", "refreshShutdownTargetOptions",
    "openShutdownTimerMenu", "ADMIN_PC_SHUTDOWN_STATE_KEY",
):
    if forbidden in html:
        raise SystemExit("Shutdown timer remnant detected after removal: " + forbidden)

for required in (
    marker, "V12.1.39-AUTO-RELAY-TARGET-ONLY", "wakeRelayCard",
    "wakeRelayVersionSupported", "wake_on_lan_relay", "admin_rental_accounts_global",
    "admin_create_rental_global", "admin_update_rental_global", "admin_disable_rental_global",
    "V12.1.37-DAILY-REPORT-KEYSET-EXPORT", "report_detailed_usage_page",
    "report_summary_compact", "freeTestPolicyCard", "admin_get_free_test_policy",
    "admin_set_free_test_policy", "ensureActiveDbRouteForAuth", "dbSyncCall('start')",
    "requestSharedDbRouteSwitch",
):
    if required not in html:
        raise SystemExit("Adjacent feature regression: missing " + required)

if "selectedDevice=rows.find(x=>x.id===selectedDeviceId)||null;renderGlobalDeviceSelector(rows);" not in html:
    raise SystemExit("PC list still does not resolve selected device before rendering global selector.")
if 'id="pairingNav"' not in html or 'id="accounts"' not in html:
    raise SystemExit("Pairing or global rental tab was unexpectedly removed.")

# Check duplicate HTML IDs after deleting the card and nav node.
ids = re.findall(r'\bid=["\']([^"\']+)', html)
duplicates = sorted({value for value in ids if ids.count(value) > 1})
if duplicates:
    raise SystemExit("Duplicate HTML IDs: " + ", ".join(duplicates))

HTML.write_text(html, encoding="utf-8")
GRADLE.write_text(gradle, encoding="utf-8")
print("PASS: Timer Shutdown PC menu/card and scheduling/cancel logic removed.")
print("PASS: FREE TEST, login, pairing, global rental, reports, WoL and dual-DB markers preserved.")
print("PASS: PC list refresh retained; Admin V12.1.40 / versionCode 68.")
