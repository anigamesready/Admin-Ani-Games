from pathlib import Path
import re

HTML = Path("android/app/src/main/assets/web/admin.html")
GRADLE = Path("android/app/build.gradle")
VERSION = Path("VERSION.txt")
html = HTML.read_text(encoding="utf-8")
gradle = GRADLE.read_text(encoding="utf-8")
MARKER = "V12.1.32-ROUTE-GET-NO-PREFLIGHT"

if MARKER in html:
    if "versionCode 60" not in gradle or "versionName '12.1.32'" not in gradle:
        raise SystemExit("V12.1.32 marker/version mismatch")
    print("PASS: V12.1.32 route GET preflight fix already applied")
    raise SystemExit(0)

if "V12.1.31-AUTH-ROUTE-FAST-CACHE" not in html:
    raise SystemExit("Expected exact Admin V12.1.31 base; refusing unknown source")
if "versionCode 59" not in gradle or "versionName '12.1.31'" not in gradle:
    raise SystemExit("Expected Admin V12.1.31 Gradle markers")

route_pattern = re.compile(r"(?ms)^async function readDualDbRoute\(target\)\{.*?^\}")
matches = list(route_pattern.finditer(html))
if len(matches) != 1:
    raise SystemExit(f"Expected exactly one readDualDbRoute function, found {len(matches)}")
fn = matches[0].group(0)
old = "method:'GET',headers:{apikey:cfg.key},cache:'no-store',signal:ctl.signal"
if fn.count(old) != 1:
    raise SystemExit(f"Expected the route GET apikey header exactly once, found {fn.count(old)}")
# db-route-status is deployed with verify_jwt=false and reads route-control through a
# server-side service credential. The browser does not need to send apikey. Removing
# this non-simple header avoids WebView CORS OPTIONS preflight, which was visible in
# logs from Android but was not followed by a GET.
fn = fn.replace(old, "method:'GET',cache:'no-store',signal:ctl.signal", 1)
html = html[:matches[0].start()] + fn + html[matches[0].end():]

marker_anchor = "// V12.1.31-AUTH-ROUTE-FAST-CACHE"
if html.count(marker_anchor) != 1:
    raise SystemExit("Expected V12.1.31 auth marker exactly once")
html = html.replace(marker_anchor, "// " + MARKER + " — make db-route-status a simple GET so Android WebView skips CORS preflight.\n" + marker_anchor, 1)

# Runtime assertions: no apikey custom header remains in this route function, and
# the route still checks both target reference and response shape with a timeout.
matches = list(route_pattern.finditer(html))
if len(matches) != 1:
    raise SystemExit("V12.1.32 route helper duplication detected")
fn = matches[0].group(0)
for token in ["'/functions/v1/db-route-status'", "cache:'no-store'", "data?.readOnly!==true", "data?.projectRef!==cfg.ref", "DB_ROUTE_STATUS_TIMEOUT:"]:
    if token not in fn:
        raise SystemExit("V12.1.32 route safety assertion missing: " + token)
if "headers:{apikey:cfg.key}" in fn:
    raise SystemExit("V12.1.32 still triggers a preflight by sending apikey")
for token in ["PRIMARY_LOGIN_DOES_NOT_REQUIRE_DB2_READY", "if(!routeBackupReady(authority))", "readDualDbRoute('backup')", "DB_ROUTE_CUTOVER_INCOMPLETE", "V12.1.30-DEVICE-LIST-INIT-FIX"]:
    if token not in html:
        raise SystemExit("Route or baseline regression marker missing: " + token)

gradle = gradle.replace("versionCode 59", "versionCode 60", 1)
gradle = gradle.replace("versionName '12.1.31'", "versionName '12.1.32'", 1)
if "versionCode 60" not in gradle or "versionName '12.1.32'" not in gradle:
    raise SystemExit("V12.1.32 version update failed")

HTML.write_text(html, encoding="utf-8")
GRADLE.write_text(gradle, encoding="utf-8")
VERSION.write_text("AniGames Admin Android V12.1.32 — removes browser apikey header from read-only route-status GET to avoid Android WebView CORS preflight; route target and DB2 cutover guards unchanged.\n", encoding="utf-8")
print("PASS: V12.1.32 avoids route-status CORS preflight from Android while preserving strict route validation and DB2 cutover guards.")
