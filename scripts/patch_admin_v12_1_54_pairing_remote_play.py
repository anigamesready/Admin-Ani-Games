from pathlib import Path
import sys

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
PAGE = ROOT / "android/app/src/main/assets/web/admin.html"
GRADLE = ROOT / "android/app/build.gradle"
MANIFEST = ROOT / "android/app/src/main/AndroidManifest.xml"
VERSION = ROOT / "VERSION.txt"
MARKER = "V12.1.54-PAIRING-REMOTE-PLAY-LABEL"

for path in (PAGE, GRADLE, MANIFEST):
    if not path.is_file():
        raise SystemExit("Required Admin V12.1.54 file missing: " + str(path))

page = PAGE.read_text(encoding="utf-8")
gradle = GRADLE.read_text(encoding="utf-8")
manifest = MANIFEST.read_text(encoding="utf-8")

if MARKER in page:
    if "🔗 Pairing Remote Play" not in page:
        raise SystemExit("V12.1.54 marker exists without expected menu label")
    if "versionCode 82" not in gradle or "versionName '12.1.54'" not in gradle:
        raise SystemExit("V12.1.54 version metadata does not match")
    print("PASS: Admin V12.1.54 Pairing Remote Play already applied")
    raise SystemExit(0)

nav_old = """<button id="remotePlayAdminNav" data-tab="remotePlay" onclick="tab('remotePlay')">🎮 Remote Play</button>"""
nav_new = """<button id="remotePlayAdminNav" data-tab="remotePlay" onclick="tab('remotePlay')">🔗 Pairing Remote Play</button>"""
if page.count(nav_old) != 1:
    raise SystemExit("Remote Play menu anchor mismatch; refusing to alter unrelated navigation")
page = page.replace(nav_old, nav_new, 1)

heading_old = '<h3 style="margin:0">🎮 Ani Remote Play</h3>'
heading_new = '<h3 style="margin:0">🔗 Pairing Remote Play</h3>'
if page.count(heading_old) != 1:
    raise SystemExit("Remote Play section heading anchor mismatch")
page = page.replace(heading_old, heading_new, 1)
page += "\n<!-- " + MARKER + " -->\n"

replacements = [
    ("versionCode 81", "versionCode 82"),
    ("versionName '12.1.53'", "versionName '12.1.54'"),
]
for old, new in replacements:
    if gradle.count(old) == 1:
        gradle = gradle.replace(old, new, 1)
    elif new not in gradle:
        raise SystemExit("Admin V12.1.54 Gradle anchor missing: " + old)
if "versionCode 82" not in gradle or "versionName '12.1.54'" not in gradle:
    raise SystemExit("Admin V12.1.54 Gradle metadata verification failed")

import re
label_new = 'android:label="AniGames Admin V12.1.54 DB Android"'
manifest, label_count = re.subn(r'android:label="[^"]+"', label_new, manifest, count=1)
if label_count != 1:
    raise SystemExit("Admin manifest must contain exactly one application label to update")

PAGE.write_text(page, encoding="utf-8")
GRADLE.write_text(gradle, encoding="utf-8")
MANIFEST.write_text(manifest, encoding="utf-8")
VERSION.write_text(
    "AniGames Admin Android V12.1.54 — Pairing Remote Play menu based on V12.1.53; DB Android API and existing connection settings preserved.\n",
    encoding="utf-8",
)
print("PASS: Admin V12.1.54 menu label and package metadata updated without changing DB/API settings.")
