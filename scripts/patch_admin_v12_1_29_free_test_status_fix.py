from pathlib import Path
import re

HTML = Path("android/app/src/main/assets/web/admin.html")
GRADLE = Path("android/app/build.gradle")
VERSION = Path("VERSION.txt")
html = HTML.read_text(encoding="utf-8")
gradle = GRADLE.read_text(encoding="utf-8")

MARKER = "V12.1.29-FREE-TEST-STATUS-FIX"
if MARKER in html:
    if "versionCode 57" not in gradle or "versionName '12.1.29'" not in gradle:
        raise SystemExit("V12.1.29 marker/version mismatch")
    print("PASS: V12.1.29 fixes already applied")
    raise SystemExit(0)

if "V12.1.28-FREE-TEST-GATE" not in html:
    raise SystemExit("Expected exact Admin V12.1.28 feature branch based on V12.1.27; refusing another baseline")
if "versionCode 56" not in gradle or "versionName '12.1.28'" not in gradle:
    raise SystemExit("Expected Admin V12.1.28 Gradle markers before status fix")
if "function schedulePcShutdown()" not in html or "function cancelPcShutdown()" not in html:
    raise SystemExit("Selected-PC shutdown timer handlers are missing")
if 'id="shutdownTargetDevice"' not in html or 'id="freeTestPolicyCard"' not in html:
    raise SystemExit("V12.1.28 policy/timer UI anchors are missing")

# Remove the previous developer-machine-specific fallback that could pick an unintended PC.
fallback = re.compile(r"\s*\|\|\s*list\.find\(d => /galtys/i\.test\(String\(d\.device_name \|\| ''\)\)\)")
html, removed = fallback.subn("", html)
if removed != 1:
    raise SystemExit(f"Expected exactly one hard-coded target fallback to remove, found {removed}")

# Default is 00:30:00 and the user can edit hours, minutes, and seconds independently.
hours_pattern = re.compile(r'(<input id="shutdownHours"[^>]*value=")\d+(")')
html, n_hours = hours_pattern.subn(r'\g<1>0\2', html, count=1)
if n_hours != 1:
    raise SystemExit("Shutdown hours control anchor mismatch")
minutes_pattern = re.compile(r'(<input id="shutdownMinutes"[^>]*value=")\d+(")')
html, n_minutes = minutes_pattern.subn(r'\g<1>30\2', html, count=1)
if n_minutes != 1:
    raise SystemExit("Shutdown minutes control anchor mismatch")
minutes_span = '<span>menit</span></div></div>'
seconds_control = '<span>menit</span><input id="shutdownSeconds" type="number" min="0" max="59" step="1" value="0" aria-label="Detik timer shutdown" style="width:90px"><span>detik</span></div></div>'
if html.count(minutes_span) != 1:
    raise SystemExit("Shutdown minutes input row anchor mismatch")
html = html.replace(minutes_span, seconds_control, 1)

duration_pattern = re.compile(r"function shutdownDurationMs\(\) \{.*?\n\}\nfunction shutdownFormatRemaining", re.S)
duration_replacement = """function shutdownDurationMs() {
 const h = Number($('shutdownHours')?.value);
 const m = Number($('shutdownMinutes')?.value);
 const s = Number($('shutdownSeconds')?.value);
 if (!Number.isInteger(h) || h < 0 || h > 24) throw new Error('Jam harus antara 0 dan 24.');
 if (!Number.isInteger(m) || m < 0 || m > 59) throw new Error('Menit harus antara 0 dan 59.');
 if (!Number.isInteger(s) || s < 0 || s > 59) throw new Error('Detik harus antara 0 dan 59.');
 const ms = ((h * 60 + m) * 60 + s) * 1000;
 if (ms < 5000) throw new Error('Durasi minimum timer adalah 5 detik.');
 if (ms > 24 * 60 * 60 * 1000) throw new Error('Durasi maksimum timer adalah 24 jam.');
 return ms;
}
function shutdownFormatRemaining"""
html, duration_count = duration_pattern.subn(duration_replacement, html, count=1)
if duration_count != 1:
    raise SystemExit("Shutdown duration parser anchor mismatch")

# Only the main Admin Owner context can see/manage the policy and timer panels. Server RPCs enforce this too.
role_anchor = "function applyPairingRoleUI(){const owner=ctx?.role==='owner';const nav=$('pairingNav');"
role_replacement = "function applyPairingRoleUI(){const owner=ctx?.role==='owner';const freeTestNav=$('freeTestPolicyNav');if(freeTestNav)freeTestNav.classList.toggle('hidden',!owner);const shutdownNav=$('shutdownTimerNav');if(shutdownNav)shutdownNav.classList.toggle('hidden',!owner);const freeTestCard=$('freeTestPolicyCard');if(freeTestCard)freeTestCard.classList.toggle('hidden',!owner);const shutdownCard=$('pcShutdownTimerCard');if(shutdownCard)shutdownCard.classList.toggle('hidden',!owner);const nav=$('pairingNav');"
if html.count(role_anchor) != 1:
    raise SystemExit("Owner role UI anchor mismatch")
html = html.replace(role_anchor, role_replacement, 1)

html = html.replace("V12.1.28-FREE-TEST-GATE", MARKER)
if "function schedulePcShutdown()" not in html or "function cancelPcShutdown()" not in html:
    raise SystemExit("Shutdown schedule/cancel handlers disappeared")
for token in (
    MARKER,
    "shutdownSeconds",
    'value="30"',
    "admin_get_free_test_policy",
    "admin_set_free_test_policy",
    "082298316902",
    "function refreshShutdownTargetOptions",
):
    if token not in html:
        raise SystemExit("V12.1.29 regression token missing: " + token)

gradle, code_count = re.subn(r"versionCode 56", "versionCode 57", gradle, count=1)
gradle, name_count = re.subn(r"versionName '12\.1\.28'", "versionName '12.1.29'", gradle, count=1)
if code_count != 1 or name_count != 1:
    raise SystemExit("Could not bump Admin APK version to 12.1.29")
VERSION.write_text("AniGames Admin Android V12.1.29 — based on the verified V12.1.27 source; owner-only FREE TEST gate, 00:30:00 default target-PC shutdown timer, seconds input, and explicit cancel/status.\n", encoding="utf-8")
HTML.write_text(html, encoding="utf-8")
GRADLE.write_text(gradle, encoding="utf-8")
print("PASS: V12.1.29 owner-only UI, 00:30:00 default timer, hour/minute/second controls, removal of hard-coded target fallback, and APK version 57.")
