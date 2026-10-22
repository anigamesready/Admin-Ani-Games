from pathlib import Path
import re

HTML = Path("android/app/src/main/assets/web/admin.html")
GRADLE = Path("android/app/build.gradle")
html = HTML.read_text(encoding="utf-8")
gradle = GRADLE.read_text(encoding="utf-8")
MARKER = "V12.1.27-LOGIN-CLICK-ROUTE-RESOLVE"

if MARKER in html:
    if "versionCode 55" not in gradle or "versionName '12.1.27'" not in gradle:
        raise SystemExit("V12.1.27 marker/version mismatch")
    print("PASS: V12.1.27 login-click route refresh already applied")
    raise SystemExit(0)

if "V12.1.26-PRIMARY-LOGIN-AUTHORITY" not in html:
    raise SystemExit("Expected V12.1.26 source; refusing to patch unknown baseline")
if "versionCode 54" not in gradle or "versionName '12.1.26'" not in gradle:
    raise SystemExit("Expected V12.1.26 Gradle markers")

# The startup attempt can fail transiently before the user presses Masuk. The old
# guard then rejected login immediately without trying to read the active route again.
# Re-read DB1's authoritative route on the user's auth action; for DB1 this does not
# require DB2 readiness. If DB2 is the active target, resolver keeps the two-project
# proof and cutover guard. Never silently fall back to a different project.
helper = r"""// V12.1.27-LOGIN-CLICK-ROUTE-RESOLVE
async function ensureActiveDbRouteForAuth(){
 try{
  const resolved=await resolveDualDbRoute(true);
  const target=String(resolved?.target||'');
  if(!['primary','backup'].includes(target))throw new Error('DB_ROUTE_INVALID_TARGET');
  // resolveDualDbRoute returns {target, epoch, switchId, route}; configure from its
  // authoritative route row so switch ID/state are not lost through the wrapper.
  configureDbTarget(target,resolved.route||resolved);
  dualDbRouteReady=true;
  dualDbRouteLocked=false;
  setAdminAuthEnabled(true);
  try{v12InitDbSwitch()}catch(_){}
  return true;
 }catch(e){
  dualDbRouteReady=false;
  const detail=String(e?.message||e||'route unavailable').slice(0,180);
  loginMsg('Route database belum valid; autentikasi belum dikirim. Detail: '+detail);
  return false;
 }
}
"""
if MARKER not in html:
    anchor = "async function login(){"
    if html.count(anchor) != 1:
        raise SystemExit(f"Expected exactly one login() anchor; found {html.count(anchor)}")
    html = html.replace(anchor, helper + "\n" + anchor, 1)

old_guard = "if(!dualDbRouteReady)return loginMsg('Rute database belum terverifikasi. Login dan perubahan akun ditahan demi keamanan.');"
if html.count(old_guard) != 3:
    raise SystemExit(f"Expected three old auth route guards (login/signup/reset), found {html.count(old_guard)}")
html = html.replace(old_guard, "if(!(await ensureActiveDbRouteForAuth()))return;", 3)

# Fix the startup call to pass the actual server route row rather than the local wrapper.
# This preserves switch_id and all server-owned route attributes in the active DB badge/state.
startup_call = "configureDbTarget(route.target,route);"
if startup_call not in html:
    raise SystemExit("Expected startup route configuration call")
html = html.replace(startup_call, "configureDbTarget(route.target,route.route||route);")

# Static checks: auth actions must re-read authoritative state and must not silently
# bypass the route guard. DB2 still goes through routeBackupReady + a second read.
for required in [
    MARKER,
    "async function ensureActiveDbRouteForAuth()",
    "resolveDualDbRoute(true)",
    "configureDbTarget(target,resolved.route||resolved)",
    "if(!(await ensureActiveDbRouteForAuth()))return;",
    "if(!routeBackupReady(authority))",
    "readDualDbRoute('backup')",
    "DB_ROUTE_CUTOVER_INCOMPLETE",
]:
    if required not in html:
        raise SystemExit("V12.1.27 safety assertion missing: " + required)
if old_guard in html:
    raise SystemExit("Legacy unconditional route lock remains")

gradle = gradle.replace("versionCode 54", "versionCode 55", 1)
gradle = gradle.replace("versionName '12.1.26'", "versionName '12.1.27'", 1)
if "versionCode 55" not in gradle or "versionName '12.1.27'" not in gradle:
    raise SystemExit("V12.1.27 version update failed")

HTML.write_text(html, encoding="utf-8")
GRADLE.write_text(gradle, encoding="utf-8")
Path("VERSION.txt").write_text(
    "AniGames Admin Android V12.1.27 — login/signup/reset refresh global active route at action time; DB1 login does not depend on DB2 readiness; DB2 remains strictly guarded\n",
    encoding="utf-8",
)
print("PASS: V12.1.27 re-reads global route when auth is requested; DB1 does not depend on DB2 status, and DB2 cutover proof remains strict.")
