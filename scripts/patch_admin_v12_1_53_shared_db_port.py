from pathlib import Path
import sys

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
PAGE = ROOT / "android/app/src/main/assets/web/admin.html"
GRADLE = ROOT / "android/app/build.gradle"
MANIFEST = ROOT / "android/app/src/main/AndroidManifest.xml"
VERSION = ROOT / "VERSION.txt"
MARKER = "V12.1.53-REMOTE-PLAY-SHARED-DB-PORT-8787"

for p in (PAGE, GRADLE, MANIFEST):
    if not p.is_file():
        raise SystemExit("Required Admin V12.1.53 project file missing: " + str(p))

page = PAGE.read_text(encoding="utf-8")
gradle = GRADLE.read_text(encoding="utf-8")
manifest = MANIFEST.read_text(encoding="utf-8")

if MARKER in page:
    print("PASS: Admin V12.1.53 shared DB API default already applied")
    raise SystemExit(0)

old_endpoint = "http://127.0.0.1:8788"
count = page.count(old_endpoint)
if count != 2:
    raise SystemExit(f"Expected exactly 2 staging API defaults (login field + local fallback), found {count}")
page = page.replace(old_endpoint, "http://127.0.0.1:8787")

old_version = "versionCode 80"
if gradle.count(old_version) != 1:
    raise SystemExit("Admin Gradle versionCode 80 anchor mismatch")
gradle = gradle.replace(old_version, "versionCode 81", 1)
old_version_name = "versionName '12.1.52'"
if gradle.count(old_version_name) != 1:
    raise SystemExit("Admin Gradle versionName 12.1.52 anchor mismatch")
gradle = gradle.replace(old_version_name, "versionName '12.1.53'", 1)

old_package = "applicationId 'com.anigames.billingadmin.v152db'"
if gradle.count(old_package) != 1:
    raise SystemExit("Admin V12.1.52 isolated package anchor mismatch")
gradle = gradle.replace(old_package, "applicationId 'com.anigames.billingadmin.v153db'", 1)

old_label = 'android:label="AniGames Admin V12.1.52 DB Android"'
if manifest.count(old_label) != 1:
    raise SystemExit("Admin V12.1.52 manifest label anchor mismatch")
manifest = manifest.replace(old_label, 'android:label="AniGames Admin V12.1.53 DB Android"', 1)

page += "\n<!-- " + MARKER + " -->\n"
if page.count("http://127.0.0.1:8787") != 2 or "http://127.0.0.1:8788" in page:
    raise SystemExit("Admin V12.1.53 API default verification failed")
if "function localApiBase()" not in page or "function saveLocalApiUrl()" not in page:
    raise SystemExit("Admin local API endpoint override was not preserved")
if "applicationId 'com.anigames.billingadmin.v153db'" not in gradle:
    raise SystemExit("Admin V12.1.53 application ID verification failed")

PAGE.write_text(page, encoding="utf-8")
GRADLE.write_text(gradle, encoding="utf-8")
MANIFEST.write_text(manifest, encoding="utf-8")
VERSION.write_text(
    "AniGames Admin Android V12.1.53 — Remote Play controls using shared DB Android API port 8787. "
    "Based on V12.1.52 Owner-only Remote Play controls.\n",
    encoding="utf-8",
)
print("PASS: Admin V12.1.53 uses DB Android shared API port 8787; custom URL override and Owner-only Remote Play controls preserved.")
