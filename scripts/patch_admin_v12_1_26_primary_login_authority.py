from pathlib import Path
import re

HTML = Path("android/app/src/main/assets/web/admin.html")
GRADLE = Path("android/app/build.gradle")
html = HTML.read_text(encoding="utf-8")
gradle = GRADLE.read_text(encoding="utf-8")
marker = "V12.1.26-PRIMARY-LOGIN-AUTHORITY"

if marker in html:
    if "versionCode 54" not in gradle or "versionName '12.1.26'" not in gradle:
        raise SystemExit("V12.1.26 marker/version mismatch")
    print("PASS: V12.1.26 primary-login authority patch already applied")
    raise SystemExit(0)

if "V12.1.25-ROUTE-BOOT-SEPARATION" not in html:
    raise SystemExit("Expected V12.1.25 source; refusing to patch an unknown baseline")
if "versionCode 53" not in gradle or "versionName '12.1.25'" not in gradle:
    raise SystemExit("Expected V12.1.25 Gradle version markers")

# DB1 is the canonical primary route authority while active_target=primary.
# DB2 readiness and its status endpoint must not be required to log into DB1.
# A transition to DB2 still requires both projects to agree and pass the full cutover proof.
new_resolver = r"""async function resolveDualDbRoute(force=false){
 if(!force&&dualDbRouteState&&Date.now()-dualDbRouteCheckedAt<DB_ROUTE_CACHE_MS)return dualDbRouteState;
 if(dualDbRoutePromise)return dualDbRoutePromise;
 dualDbRoutePromise=(async()=>{
  let authority;
  try{authority=await readDualDbRoute('primary')}
  catch(e){throw new Error('DB_ROUTE_STATUS_UNAVAILABLE: DB1 primary route authority cannot be verified; '+String(e?.message||e).slice(0,100))}
  if(!authority)throw new Error('DB_ROUTE_STATUS_UNAVAILABLE: DB1 primary route authority cannot be verified');
  const target=String(authority.active_target||'');
  if(!['primary','backup'].includes(target))throw new Error('DB_ROUTE_INVALID_TARGET: DB1 returned an unknown active target');
  if(target==='primary'){
   // PRIMARY_LOGIN_DOES_NOT_REQUIRE_DB2_READY
   if(authority.primary_ready!==true)throw new Error('DB_ROUTE_PRIMARY_NOT_READY: DB1 is selected but primary_ready is false');
   // Important: primary login/operations stay on DB1 even when DB2 is not yet ready,
   // has no parity proof, or its read-only status endpoint is temporarily unavailable.
   // Cutover and Sync functions keep their own two-project consistency/readiness checks.
   return rememberDualDbRoute('primary',authority);
  }

  // DB1 reports that the global active target is DB2. This path remains strict:
  // both independently stored route records must match and DB2 cutover proof must be current.
  if(!routeBackupReady(authority))throw new Error('DB_ROUTE_CUTOVER_BLOCKED: DB2 is selected but parity/readiness/schema/cutover proof is not current');
  let backup;
  try{backup=await readDualDbRoute('backup')}
  catch(e){throw new Error('DB_ROUTE_CUTOVER_INCOMPLETE: DB1 points to DB2 but DB2 route status cannot be verified; '+String(e?.message||e).slice(0,100))}
  if(backup.active_target!==target||Number(backup.epoch)!==Number(authority.epoch)||String(backup.switch_id||'')!==String(authority.switch_id||''))
   throw new Error('DB_ROUTE_CUTOVER_INCOMPLETE: DB1 and DB2 target, epoch, or switch ID differ');
  if(!routeBackupReady(backup))throw new Error('DB_ROUTE_CUTOVER_BLOCKED: DB2 cutover proof is not current on both projects');
  return rememberDualDbRoute('backup',backup);
 })();
 try{return await dualDbRoutePromise}finally{dualDbRoutePromise=null}
}"""
pattern = re.compile(r"(?ms)^async function resolveDualDbRoute\(force=false\)\{.*?^\}")
matches = list(pattern.finditer(html))
if len(matches) != 1:
    raise SystemExit(f"Expected exactly one resolveDualDbRoute function, found {len(matches)}")
html = html[:matches[0].start()] + new_resolver + html[matches[0].end():]

# Reflect the trust boundary accurately in the visible badge without changing the selected DB.
old_badge = "if(system){system.textContent='RUTE GLOBAL TERVERIFIKASI';system.style.color='var(--ok)';system.style.borderColor='var(--ok)'}"
new_badge = "if(system){system.textContent=DB_TARGET==='backup'?'RUTE GLOBAL TERVERIFIKASI':'DB1 PRIMARY TERVERIFIKASI';system.style.color='var(--ok)';system.style.borderColor='var(--ok)'}"
if html.count(old_badge) != 1:
    raise SystemExit(f"Expected exactly one route badge assignment, found {html.count(old_badge)}")
html = html.replace(old_badge, new_badge, 1)

old_hint = "if(hint)hint.textContent='Target mengikuti route-control Supabase • epoch '+DB_ROUTE_EPOCH+' • switch '+(DB_ROUTE_SWITCH_ID||'awal')"
new_hint = "if(hint)hint.textContent=(DB_TARGET==='backup'?'Target DB2 dikonfirmasi kedua route-control':'Login utama mengikuti route-control DB1; kesiapan DB2 hanya memblokir cutover')+' • epoch '+DB_ROUTE_EPOCH+' • switch '+(DB_ROUTE_SWITCH_ID||'awal')"
if html.count(old_hint) != 1:
    raise SystemExit(f"Expected exactly one route hint assignment, found {html.count(old_hint)}")
html = html.replace(old_hint, new_hint, 1)

# Static safety contract: preserve strict DB2 cutover checks, avoid toggling readiness flags in DB data.
for required in [
    "PRIMARY-LOGIN-AUTHORITY",
    "if(target==='primary')",
    "PRIMARY_LOGIN_DOES_NOT_REQUIRE_DB2_READY",
    "authority.primary_ready!==true",
    "if(!routeBackupReady(authority))",
    "readDualDbRoute('backup')",
    "DB_ROUTE_CUTOVER_INCOMPLETE",
    "DB_ROUTE_CUTOVER_BLOCKED",
    "DB1 PRIMARY TERVERIFIKASI",
]:
    if required not in html:
        raise SystemExit("Required V12.1.26 safety marker missing: " + required)
# Marker inserted alongside the new resolver for the build's explicit version proof.
html = html.replace("async function resolveDualDbRoute(force=false){",
                    "// " + marker + "\nasync function resolveDualDbRoute(force=false){", 1)
if html.count(marker) != 1:
    raise SystemExit("V12.1.26 marker insertion failed")

gradle = gradle.replace("versionCode 53", "versionCode 54", 1)
gradle = gradle.replace("versionName '12.1.25'", "versionName '12.1.26'", 1)
if "versionCode 54" not in gradle or "versionName '12.1.26'" not in gradle:
    raise SystemExit("V12.1.26 version bump failed")

HTML.write_text(html, encoding="utf-8")
GRADLE.write_text(gradle, encoding="utf-8")
Path("VERSION.txt").write_text(
    "AniGames Admin Android V12.1.26 — DB1 primary route authorizes login while DB2 readiness remains a cutover-only guard; DB2 cutover still requires matching route proofs\n",
    encoding="utf-8",
)
print("PASS: V12.1.26 lets login follow active DB1 authority without requiring DB2 readiness; active DB2 path retains two-project cutover proof.")
