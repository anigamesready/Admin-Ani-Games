from pathlib import Path

HTML = Path("android/app/src/main/assets/web/admin.html")
GRADLE = Path("android/app/build.gradle")
VERSION = Path("VERSION.txt")

html = HTML.read_text(encoding="utf-8")
gradle = GRADLE.read_text(encoding="utf-8")

MARKER = "V12.1.30-DEVICE-LIST-INIT-FIX"
if MARKER in html:
    if "versionCode 58" not in gradle or "versionName '12.1.30'" not in gradle:
        raise SystemExit("V12.1.30 marker/version mismatch")
    print("PASS: V12.1.30 device-list initialization fix already applied")
    raise SystemExit(0)

if "V12.1.29-FREE-TEST-STATUS-FIX" not in html:
    raise SystemExit("Expected exact Admin V12.1.29 baseline; refusing another source")
if "versionCode 57" not in gradle or "versionName '12.1.29'" not in gradle:
    raise SystemExit("Expected Admin V12.1.29 Gradle markers")
if html.count("devicesCache=rows;refreshShutdownTargetOptions(rows);renderRecoveryDeviceOptions();") != 1:
    raise SystemExit("Expected exactly one early shutdown-target refresh call")
if html.count("selectedDevice=rows.find(x=>x.id===selectedDeviceId)||null;renderGlobalDeviceSelector(rows);") != 1:
    raise SystemExit("Expected exactly one selected-device resolution anchor")

# loadDevices() must first restore/resolve selectedDeviceId, then populate the
# add-on's shutdown target dropdown. The previous order threw a ReferenceError
# on startup and stopped the rest of the PC list from rendering.
html = html.replace(
    "devicesCache=rows;refreshShutdownTargetOptions(rows);renderRecoveryDeviceOptions();",
    "devicesCache=rows;renderRecoveryDeviceOptions();",
    1,
)
html = html.replace(
    "selectedDevice=rows.find(x=>x.id===selectedDeviceId)||null;renderGlobalDeviceSelector(rows);",
    "selectedDevice=rows.find(x=>x.id===selectedDeviceId)||null;refreshShutdownTargetOptions(rows);renderGlobalDeviceSelector(rows);",
    1,
)

if html.count("refreshShutdownTargetOptions(rows)") != 1:
    raise SystemExit("Device-list fix assertion failed: expected one deferred target refresh")
early = html.find("devicesCache=rows;renderRecoveryDeviceOptions();")
resolved = html.find("selectedDevice=rows.find(x=>x.id===selectedDeviceId)||null;refreshShutdownTargetOptions(rows);")
if early < 0 or resolved <= early:
    raise SystemExit("Device-list fix assertion failed: target refresh does not follow selected-device resolution")

html = html.replace(
    "function refreshShutdownTargetOptions(rows) {",
    "// " + MARKER + " — resolve PC selection before initializing addon target list.\nfunction refreshShutdownTargetOptions(rows) {",
    1,
)
gradle = gradle.replace("versionCode 57", "versionCode 58", 1)
gradle = gradle.replace("versionName '12.1.29'", "versionName '12.1.30'", 1)
if "versionCode 58" not in gradle or "versionName '12.1.30'" not in gradle:
    raise SystemExit("V12.1.30 version update failed")

HTML.write_text(html, encoding="utf-8")
GRADLE.write_text(gradle, encoding="utf-8")
VERSION.write_text(
    "AniGames Admin Android V12.1.30 — fixes PC list rendering by initializing shutdown target options only after the active PC selection is resolved; preserves V12.1.27 base behavior and V12.1.28–V12.1.29 features.\n",
    encoding="utf-8",
)
print("PASS: V12.1.30 defers shutdown-target initialization until selectedDeviceId is resolved; existing PC list flow is preserved.")
