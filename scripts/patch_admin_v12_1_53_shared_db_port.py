from pathlib import Path
import sys

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
WEB = ROOT / "android/app/src/main/assets/web"
GRADLE = ROOT / "android/app/build.gradle"
VERSION = ROOT / "VERSION.txt"
MARKER = "V12.1.53-REMOTE-PLAY-SHARED-DB-PORT-8787"

pages = {
    "index.html": 2,
    "admin-control.html": 1,
    "admin.html": 2,
}
for name, expected in pages.items():
    path = WEB / name
    if not path.is_file():
        raise SystemExit("Admin V12.1.53 page missing: " + str(path))
    page = path.read_text(encoding="utf-8")
    if name == "admin.html" and MARKER in page:
        if "http://127.0.0.1:8787" not in page or "http://127.0.0.1:8788" in page:
            raise SystemExit("Existing V12.1.53 marker does not match port 8787")
        continue
    count = page.count("http://127.0.0.1:8788")
    if count != expected:
        raise SystemExit(f"{name}: expected {expected} staging API defaults, found {count}")
    page = page.replace("http://127.0.0.1:8788", "http://127.0.0.1:8787")
    if "http://127.0.0.1:8788" in page or page.count("http://127.0.0.1:8787") < expected:
        raise SystemExit(name + ": port 8787 replacement verification failed")
    if name == "admin.html":
        page += "\n<!-- " + MARKER + " -->\n"
    path.write_text(page, encoding="utf-8")

if not GRADLE.is_file():
    raise SystemExit("Admin V12.1.53 Gradle file missing")
gradle = GRADLE.read_text(encoding="utf-8")
replacements = [
    ("versionCode 80", "versionCode 81"),
    ("versionName '12.1.52'", "versionName '12.1.53'"),

]
for old, new in replacements:
    if gradle.count(old) == 1:
        gradle = gradle.replace(old, new, 1)
    elif new not in gradle:
        raise SystemExit("Admin Gradle metadata anchor missing: " + old)
if "versionCode 81" not in gradle or "versionName '12.1.53'" not in gradle:
    raise SystemExit("Admin V12.1.53 version metadata verification failed")
GRADLE.write_text(gradle, encoding="utf-8")
VERSION.write_text(
    "AniGames Admin Android V12.1.53 — Remote Play owner controls using the shared DB Android API on localhost port 8787.\n",
    encoding="utf-8",
)
print("PASS: Admin V12.1.53 points login, Billing Control and Remote Play to shared DB Android port 8787.")
