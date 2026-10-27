from pathlib import Path
import re

HTML = Path("android/app/src/main/assets/web/admin.html")
GRADLE = Path("android/app/build.gradle")
VERSION = Path("VERSION.txt")

html = HTML.read_text(encoding="utf-8")
gradle = GRADLE.read_text(encoding="utf-8")
MARKER = "V12.1.31-AUTH-ROUTE-FAST-CACHE"

if MARKER in html:
    if "versionCode 59" not in gradle or "versionName '12.1.31'" not in gradle:
        raise SystemExit("V12.1.31 marker/version mismatch")
    print("PASS: V12.1.31 route-auth fast-cache patch already applied")
    raise SystemExit(0)

if "V12.1.30-DEVICE-LIST-INIT-FIX" not in html:
    raise SystemExit("Expected exact V12.1.30 baseline; refusing unknown source")
if "versionCode 58" not in gradle or "versionName '12.1.30'" not in gradle:
    raise SystemExit("Expected Admin V12.1.30 Gradle markers")
if html.count("const DB_ROUTE_CACHE_MS=5000;") != 1:
    raise SystemExit("Expected exactly one original 5-second DB route cache setting")

# The login action previously forced a duplicate route read even when startup and
# the 10-second monitor already held a recently verified authoritative route.
# Use a short 15-second cache; the live monitor still performs forced route checks
# every 10 seconds and DB2 remains protected by the strict two-project proof.
html = html.replace("const DB_ROUTE_CACHE_MS=5000;", "const DB_ROUTE_CACHE_MS=15000;", 1)

# Replace only the route request helper to produce a useful timeout diagnostic
# instead of WebView's vague "signal is aborted without reason".
read_pattern = re.compile(r"(?ms)^async function readDualDbRoute\(target\)\{.*?^\}")
read_matches = list(read_pattern.finditer(html))
if len(read_matches) != 1:
    raise SystemExit(f"Expected exactly one readDualDbRoute, found {len(read_matches)}")
read_fn = r"""async function readDualDbRoute(target){
 const cfg=target==='backup'?{ref:'xcdbipgsvohesxhxydep',url:DB2_URL,key:DB2_ROUTE_KEY}:{ref:'wzkjpycjizexxcxrfdvr',url:DB1_URL,key:DB1_ROUTE_KEY};
 const ctl=new AbortController();let timedOut=false;const timer=setTimeout(()=>{timedOut=true;ctl.abort()},4500);
 try{
  const response=await fetch(cfg.url+'/functions/v1/db-route-status',{method:'GET',headers:{apikey:cfg.key},cache:'no-store',signal:ctl.signal});
  const data=await response.json().catch(()=>({}));
  if(!response.ok||data?.ok!==true||data?.readOnly!==true||data?.projectRef!==cfg.ref||!data?.route)throw new Error('DB_ROUTE_STATUS_UNAVAILABLE:'+target);
  return data.route;
 }catch(e){
  if(timedOut||e?.name==='AbortError')throw new Error('DB_ROUTE_STATUS_TIMEOUT:'+target+' (4500ms)');
  throw e;
 }finally{clearTimeout(timer)}
}"""
html = html[:read_matches[0].start()] + read_fn + html[read_matches[0].end():]

# On auth, allow resolveDualDbRoute() to reuse a recently verified route from
# startup/monitor instead of always forcing another network request. If there is
# no recent verified route, the resolver still reads DB1 authority; if DB2 is
# active it still requires fresh, matching route-control records from both DBs.
auth_pattern = re.compile(r"(?ms)^async function ensureActiveDbRouteForAuth\(\)\{.*?^\}")
auth_matches = list(auth_pattern.finditer(html))
if len(auth_matches) != 1:
    raise SystemExit(f"Expected exactly one ensureActiveDbRouteForAuth, found {len(auth_matches)}")
auth_fn = html[auth_matches[0].start():auth_matches[0].end()]
if auth_fn.count("resolveDualDbRoute(true)") != 1:
    raise SystemExit("Expected one forced route read in auth handler")
auth_fn = auth_fn.replace(
    "async function ensureActiveDbRouteForAuth(){",
    "// " + MARKER + " — use recent verified active-route state for fast login; stale/missing state still revalidates.\\nasync function ensureActiveDbRouteForAuth(){",
    1,
)
auth_fn = auth_fn.replace("resolveDualDbRoute(true)", "resolveDualDbRoute(false)", 1)
html = html[:auth_matches[0].start()] + auth_fn + html[auth_matches[0].end():]

# Version update and regression guards.
for required in [
    MARKER,
    "const DB_ROUTE_CACHE_MS=15000;",
    "resolveDualDbRoute(false)",
    "DB_ROUTE_STATUS_TIMEOUT:",
    "if(!routeBackupReady(authority))",
    "readDualDbRoute('backup')",
    "DB_ROUTE_CUTOVER_INCOMPLETE",
    "PRIMARY_LOGIN_DOES_NOT_REQUIRE_DB2_READY",
    "V12.1.30-DEVICE-LIST-INIT-FIX",
    "function loadDevices(",
]:
    if required not in html:
        raise SystemExit("V12.1.31 safety/regression assertion missing: " + required)
auth_match = re.search(r"(?ms)^async function ensureActiveDbRouteForAuth\(\)\{.*?^\}", html)
if not auth_match or "resolveDualDbRoute(true)" in auth_match.group(0):
    raise SystemExit("V12.1.31 auth handler still forces a duplicate route check")
if html.count("function resolveDualDbRoute") != 1:
    raise SystemExit("Route resolver was duplicated")

gradle = gradle.replace("versionCode 58", "versionCode 59", 1)
gradle = gradle.replace("versionName '12.1.30'", "versionName '12.1.31'", 1)
if "versionCode 59" not in gradle or "versionName '12.1.31'" not in gradle:
    raise SystemExit("V12.1.31 version update failed")

HTML.write_text(html, encoding="utf-8")
GRADLE.write_text(gradle, encoding="utf-8")
VERSION.write_text(
    "AniGames Admin Android V12.1.31 — faster login by reusing a recently verified active DB route; 10-second route monitor and strict DB2 cutover proofs remain; route timeout diagnostics improved.\n",
    encoding="utf-8",
)
print("PASS: V12.1.31 login reuses recent authoritative route state and avoids an unnecessary forced read; DB2 safety checks preserved.")
