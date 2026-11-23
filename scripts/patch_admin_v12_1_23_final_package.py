from pathlib import Path
import re

HTML = Path("android/app/src/main/assets/web/admin.html")
GRADLE = Path("android/app/build.gradle")
MANIFEST = Path("android/app/src/main/AndroidManifest.xml")
VERSION = Path("VERSION.txt")
MARKER = "V12.1.23-FINAL-ADMIN-PACKAGE"

html = HTML.read_text(encoding="utf-8")
gradle = GRADLE.read_text(encoding="utf-8")
manifest = MANIFEST.read_text(encoding="utf-8")

if MARKER in html:
    if "applicationId 'com.anigames.billingadmin'" not in gradle:
        raise SystemExit("Final marker exists but Android applicationId is incorrect.")
    if "versionCode 51" not in gradle or "versionName '12.1.23'" not in gradle:
        raise SystemExit("Final marker exists but Gradle version is incorrect.")
    if "AniGames Admin V12 Test" in manifest:
        raise SystemExit("Test launcher label remains.")
    print("PASS: Admin V12.1.23 final package patch already applied.")
    raise SystemExit(0)

if "V12.1.22-FULL-12-TABLE-INCREMENTAL-SYNC" not in html:
    raise SystemExit("Expected Admin V12.1.22 source; refusing to patch unknown build.")
if "versionCode 50" not in gradle or "versionName '12.1.22'" not in gradle:
    raise SystemExit("Expected Admin V12.1.22 Gradle metadata.")

app_id_pattern = re.compile(r"""(?m)^(\s*applicationId\s+)["']com\.anigames\.billingadmin\.v12test["']\s*$""")
gradle, app_id_count = app_id_pattern.subn(r"\1'com.anigames.billingadmin'", gradle, count=1)
if app_id_count != 1:
    raise SystemExit(f"Expected one test applicationId com.anigames.billingadmin.v12test, found {app_id_count}.")
if "namespace 'com.anigames.billingadmin'" not in gradle:
    raise SystemExit("Unexpected Android namespace; refusing to change package identity.")

label_pattern = re.compile(r"""android:label\s*=\s*["']AniGames Admin V12 Test["']""")
manifest, label_count = label_pattern.subn('android:label="AniGames Admin"', manifest, count=1)
if label_count != 1:
    raise SystemExit(f"Expected one test launcher label, found {label_count}.")

if "applicationId 'com.anigames.billingadmin'" not in gradle:
    raise SystemExit("Stable Admin applicationId insertion failed.")
gradle = gradle.replace("versionCode 50", "versionCode 51", 1)
gradle = gradle.replace("versionName '12.1.22'", "versionName '12.1.23'", 1)

html = html.replace("// V12.1.22-FULL-12-TABLE-INCREMENTAL-SYNC",
                    "// V12.1.22-FULL-12-TABLE-INCREMENTAL-SYNC\n// " + MARKER, 1)
if html.count(MARKER) != 1:
    raise SystemExit("Final release marker insertion failed.")
if "AniGames Admin V12 Test" in manifest:
    raise SystemExit("Test launcher label remained after patch.")
if "com.anigames.billingadmin.v12test" in gradle:
    raise SystemExit("Test applicationId remained after patch.")
if "versionCode 51" not in gradle or "versionName '12.1.23'" not in gradle:
    raise SystemExit("Final version metadata check failed.")

HTML.write_text(html, encoding="utf-8")
GRADLE.write_text(gradle, encoding="utf-8")
MANIFEST.write_text(manifest, encoding="utf-8")
VERSION.write_text("AniGames Admin Android V12.1.23 FINAL — com.anigames.billingadmin; incremental 12-table Sync + row/hash preflight + Owner login + Gateway guarded cutover\n", encoding="utf-8")
print("PASS: Admin V12.1.23 final applicationId, launcher label and version metadata validated.")
