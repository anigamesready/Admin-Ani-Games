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

def remove_js_function(source: str, signature: str) -> str:
    if source.count(signature) != 1:
        raise SystemExit("Expected exactly one timer function: " + signature)
    start = source.find(signature)
    brace = source.find("{", start + len(signature) - 1)
    if brace < 0:
        raise SystemExit("Missing opening brace for " + signature)

    depth = 0
    quote = None
    escaped = False
    line_comment = False
    block_comment = False
    i = brace
    while i < len(source):
        ch = source[i]
        nxt = source[i + 1] if i + 1 < len(source) else ""
        if line_comment:
            if ch == "\n":
                line_comment = False
        elif block_comment:
            if ch == "*" and nxt == "/":
                block_comment = False
                i += 1
        elif quote:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = None
        elif ch == "/" and nxt == "/":
            line_comment = True
            i += 1
        elif ch == "/" and nxt == "*":
            block_comment = True
            i += 1
        elif ch in ("'", '"', "`"):
            quote = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                while end < len(source) and source[end] in " \t":
                    end += 1
                if end < len(source) and source[end] == "\n":
                    end += 1
                return source[:start] + source[end:]
        i += 1
    raise SystemExit("Unclosed JavaScript function: " + signature)

# Remove only the timer UI card and dedicated navigation entry.
card_start = html.find('<div class="card" id="pcShutdownTimerCard"')
if card_start < 0:
    raise SystemExit("Shutdown timer card start is missing.")
div_tags = re.finditer(r"</?div\\b[^>]*>", html[card_start:], re.I)
depth = 0
card_end = -1
for tag in div_tags:
    if tag.group(0).lower().startswith("</"):
        depth -= 1
    else:
        depth += 1
    if depth == 0:
        card_end = card_start + tag.end()
        break
if card_end < 0:
    raise SystemExit("Could not isolate the exact closing div of the shutdown timer card.")
card = html[card_start:card_end]
if "shutdownHours" not in card or "shutdownMinutes" not in card or "shutdownSeconds" not in card:
    raise SystemExit("Timer card does not match the expected hour/minute/second UI.")
html = html[:card_start] + html[card_end:]

nav = '<button id="shutdownTimerNav" onclick="openShutdownTimerMenu()">⏱️ Timer Shutdown PC</button>'
if html.count(nav) != 1:
    raise SystemExit("Expected exactly one dedicated Timer Shutdown PC navigation entry.")
html = html.replace(nav, "", 1)

# Remove timer-specific functions one at a time. Do not cut through adjacent
# command, restart-queue or PC-list functions that may share the same script area.
timer_functions = (
    "function openShutdownTimerMenu() {",
    "function readAdminShutdownStates() {",
    "function saveAdminShutdownStates(value) {",
    "function shutdownDurationMs() {",
    "function shutdownFormatRemaining(ms) {",
    "function selectedShutdownTarget() {",
    "function refreshShutdownTargetOptions(rows) {",
    "function activeRentalShutdownBlocker(device) {",
    "function effectiveShutdownTimerState(device) {",
    "function updateShutdownTimerStatus() {",
    "function previewPcShutdown() {",
    "async function schedulePcShutdown() {",
    "async function cancelPcShutdown() {",
)
for signature in timer_functions:
    html = remove_js_function(html, signature)

state_key = "const ADMIN_PC_SHUTDOWN_STATE_KEY = 'ani_games_admin_shutdown_timer_v1';"
if html.count(state_key) != 1:
    raise SystemExit("Shutdown timer local state key anchor mismatch.")
html = html.replace(state_key, "", 1)

interval = re.compile(
    r"if\s*\(!window\.__aniShutdownTimerStatusInterval\)\s*\{\s*"
    r"window\.__aniShutdownTimerStatusInterval\s*=\s*window\.setInterval\(updateShutdownTimerStatus,\s*1000\);\s*\}",
    re.S,
)
html, interval_count = interval.subn("", html, count=1)
if interval_count != 1:
    raise SystemExit("Shutdown countdown refresh interval anchor mismatch.")

# Remove timer-only role toggles but preserve Owner gating for FREE TEST.
for fragment in (
    "const shutdownNav=$('shutdownTimerNav');if(shutdownNav)shutdownNav.classList.toggle('hidden',!owner);",
    "const shutdownCard=$('pcShutdownTimerCard');if(shutdownCard)shutdownCard.classList.toggle('hidden',!owner);",
):
    if html.count(fragment) != 1:
        raise SystemExit("Timer-only role-gating fragment count mismatch.")
    html = html.replace(fragment, "", 1)

call = "refreshShutdownTargetOptions(rows);"
if html.count(call) != 1:
    raise SystemExit("Expected exactly one timer-only device dropdown refresh call.")
html = html.replace(call, "", 1)

gradle, c = re.subn(r"\bversionCode\s+67\b", "versionCode 68", gradle, count=1)
gradle, n = re.subn(r"versionName\s*'12\.1\.39'", "versionName '12.1.40'", gradle, count=1)
if c != 1 or n != 1:
    raise SystemExit("Could not safely update V12.1.39 Gradle version metadata.")

html = html.replace(
    "V12.1.39-AUTO-RELAY-TARGET-ONLY",
    "V12.1.39-AUTO-RELAY-TARGET-ONLY • " + marker,
    1,
)
VERSION.write_text(
    "AniGames Admin Android V12.1.40 — removes Admin PC shutdown countdown UI and scheduling/cancel commands. Keeps login, pairing/recovery, PC controls, FREE TEST, reseller, global rental, reports, WoL and dual-DB routing.\n",
    encoding="utf-8",
)

for forbidden in (
    "pcShutdownTimerCard", "shutdownTimerNav", "shutdownHours", "shutdownMinutes",
    "shutdownSeconds", "schedulePcShutdown", "cancelPcShutdown",
    "schedule_shutdown", "cancel_shutdown_timer", "refreshShutdownTargetOptions",
    "openShutdownTimerMenu", "ADMIN_PC_SHUTDOWN_STATE_KEY",
    "__aniShutdownTimerStatusInterval",
):
    if forbidden in html:
        raise SystemExit("Shutdown timer remnant detected after removal: " + forbidden)

for required in (
    marker, "V12.1.39-AUTO-RELAY-TARGET-ONLY", "wakeRelayCard",
    "wakeRelayVersionSupported", "wake_on_lan_relay", "wakeRelayCard", "Nyalakan PC yang Dipilih", "admin_rental_accounts_global",
    "admin_create_rental_global", "admin_update_rental_global", "admin_disable_rental_global",
    "V12.1.37-DAILY-REPORT-KEYSET-EXPORT", "report_detailed_usage_page",
    "report_summary_compact", "freeTestPolicyCard", "admin_get_free_test_policy",
    "admin_set_free_test_policy", "ensureActiveDbRouteForAuth", "dbSyncCall('start')",
    "requestSharedDbRouteSwitch", "offlineRestart=command==='restart_billing'",
    "Perintah Restart Billing masuk antrean",
):
    if required not in html:
        raise SystemExit("Adjacent feature regression: missing " + required)

if "selectedDevice=rows.find(x=>x.id===selectedDeviceId)||null;renderGlobalDeviceSelector(rows);" not in html:
    raise SystemExit("PC list still does not resolve selected device before rendering global selector.")
if 'id="pairingNav"' not in html or 'id="accounts"' not in html:
    raise SystemExit("Pairing or global rental tab was unexpectedly removed.")

ids = re.findall(r'\bid=["\']([^"\']+)', html)
duplicates = sorted({value for value in ids if ids.count(value) > 1})
if duplicates:
    raise SystemExit("Duplicate HTML IDs: " + ", ".join(duplicates))

HTML.write_text(html, encoding="utf-8")
GRADLE.write_text(gradle, encoding="utf-8")
print("PASS: Timer Shutdown PC menu/card and only timer-specific JavaScript functions removed.")
print("PASS: Restart queue, FREE TEST, login, pairing, PC controls, global rental, reports, WoL and dual-DB preserved.")
print("PASS: PC list refresh retained; Admin V12.1.40 / versionCode 68.")
