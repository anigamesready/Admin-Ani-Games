#!/usr/bin/env python3
"""V12.1.51: restore the missing Admin auth-button gate used by local API startup/login."""
from pathlib import Path
import re
import sys

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
HTML = ROOT / "android/app/src/main/assets/web/admin.html"
GRADLE = ROOT / "android/app/build.gradle"
MANIFEST = ROOT / "android/app/src/main/AndroidManifest.xml"
VERSION = ROOT / "VERSION_ADMIN_ANDROID.txt"

for path in (HTML, GRADLE, MANIFEST):
    if not path.is_file():
        raise SystemExit("ADMIN_V12_1_51_SOURCE_NOT_FOUND: " + str(path))

html = HTML.read_text(encoding="utf-8")
gradle = GRADLE.read_text(encoding="utf-8")
manifest = MANIFEST.read_text(encoding="utf-8")
MARKER = "V12.1.51-ADMIN-LOGIN-AUTH-GATE"

if MARKER in html:
    if "versionCode 79" not in gradle or "versionName '12.1.51'" not in gradle:
        raise SystemExit("V12.1.51 marker/version mismatch")
    print("PASS: V12.1.51 login gate patch already applied")
    raise SystemExit(0)

# The prior DB Android adapter calls this helper from startup, server-health
# checks, and the Login click path, but omitted its implementation entirely.
if html.count("setAdminAuthEnabled(") < 3:
    raise SystemExit("Expected the original local Admin startup/auth call sites")
if re.search(r"(?m)^function\s+setAdminAuthEnabled\s*\(", html):
    raise SystemExit("Unexpected existing setAdminAuthEnabled definition; inspect before patching")

anchor = "async function ensureActiveDbRouteForAuth(){"
if html.count(anchor) != 1:
    raise SystemExit("Expected exactly one local API auth readiness function")

helper = r"""// V12.1.51-ADMIN-LOGIN-AUTH-GATE
// The local DB adapter calls this from startup, URL health checks and login.
// Keep it intentionally small: it only controls the primary Admin login action.
function setAdminAuthEnabled(enabled){
 const button=document.querySelector('#login button.primary');
 if(!button)return;
 const active=Boolean(enabled);
 button.disabled=!active;
 button.setAttribute('aria-disabled',String(!active));
}
"""
html = html.replace(anchor, helper + "\n" + anchor, 1)

# Preserve the existing local API contract: Admin password login goes to the
# Redmi API, and the Supabase client remains solely the separate relay sidecar.
for required in (
    "async function ensureActiveDbRouteForAuth()",
    "localJson('/health',null,'GET')",
    "localJson('/auth/v1/token?grant_type=password'",
    "await boot()",
    "const RELAY_RPC_NAMES=new Set(",
    "startLocalAdmin();",
):
    if required not in html:
        raise SystemExit("V12.1.51 local-auth regression assertion missing: " + required)
if "startDualDbAdmin();" in html:
    raise SystemExit("DB1/DB2 startup unexpectedly returned to DB Android build")

# Bump only the isolated DB Android Admin build identity; preserve package ID.
gradle, code_count = re.subn(r"\bversionCode\s+78\b", "versionCode 79", gradle, count=1)
gradle, name_count = re.subn(r"versionName\s*'12\.1\.50'", "versionName '12.1.51'", gradle, count=1)
if code_count != 1 or name_count != 1:
    raise SystemExit("V12.1.51 Gradle version anchor mismatch")

label_old = 'android:label="AniGames Admin V12.1.50 DB Android"'
label_new = 'android:label="AniGames Admin V12.1.51 DB Android"'
if manifest.count(label_new) == 1:
    pass
elif manifest.count(label_old) == 1:
    manifest = manifest.replace(label_old, label_new, 1)
else:
    raise SystemExit("V12.1.51 manifest label anchor mismatch")

if "setAdminAuthEnabled" not in html or html.count(MARKER) != 1:
    raise SystemExit("V12.1.51 helper insertion failed")
if html.count("function setAdminAuthEnabled(") != 1:
    raise SystemExit("V12.1.51 helper is not unique")

HTML.write_text(html, encoding="utf-8")
GRADLE.write_text(gradle, encoding="utf-8")
MANIFEST.write_text(manifest, encoding="utf-8")
VERSION.write_text(
    "AniGames Admin Android V12.1.51 DB Android — restores missing setAdminAuthEnabled helper so local server readiness and Masuk click can proceed.\\n",
    encoding="utf-8",
)
print("PASS: missing setAdminAuthEnabled helper restored.")
print("PASS: local API login and startup adapter retained.")
print("PASS: relay sidecar remains separate.")
print("PASS: package ID preserved; version is 12.1.51 / versionCode 79.")
